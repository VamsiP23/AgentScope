#!/usr/bin/env python3
"""Fetch and print a Jaeger trace as a readable call tree."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from urllib.parse import urlencode
from urllib.request import urlopen


def fetch_trace(jaeger_url: str, trace_id: str) -> dict:
    url = f"{jaeger_url.rstrip('/')}/api/traces/{trace_id}"
    with urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_latest_trace_id(jaeger_url: str, service: str, limit: int) -> str:
    params = urlencode({"service": service, "limit": limit, "lookback": "1h"})
    url = f"{jaeger_url.rstrip('/')}/api/traces?{params}"
    with urlopen(url, timeout=10) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    traces = payload.get("data", [])
    if not traces:
        raise RuntimeError(f"No traces found for service '{service}'.")

    for trace in traces:
        spans = trace.get("spans", [])
        operation_names = {span.get("operationName", "") for span in spans}
        if any("TraceService/Export" in name for name in operation_names):
            continue
        return trace.get("traceID", "")

    raise RuntimeError(
        f"Only exporter traces were found for service '{service}'. Try generating more application traffic."
    )


def service_name_for_span(trace: dict, span: dict) -> str:
    process_id = span.get("processID", "")
    processes = trace.get("processes", {})
    return processes.get(process_id, {}).get("serviceName", "unknown")


def span_attr(span: dict, key: str, default: str = "") -> str:
    for tag in span.get("tags", []) or []:
        if tag.get("key") == key:
            return str(tag.get("value", default))
    return default


def print_span(trace: dict, span: dict, children: dict[str, list[dict]], indent: int = 0) -> None:
    service = service_name_for_span(trace, span)
    name = span.get("operationName", "unknown")
    duration_us = int(span.get("duration", 0))
    duration_ms = duration_us / 1000.0
    status = span_attr(span, "rpc.grpc.status_code") or span_attr(span, "http.status_code") or "ok"
    print("  " * indent + f"- {service}: {name} [{duration_ms:.2f}ms, status={status}]")
    for child in children.get(span.get("spanID", ""), []):
        print_span(trace, child, children, indent + 1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Show a Jaeger trace as a call tree.")
    parser.add_argument("trace_id", nargs="?", help="Jaeger trace ID")
    parser.add_argument("--jaeger-url", default="http://localhost:16686")
    parser.add_argument("--latest", action="store_true", help="Fetch the latest trace for a service")
    parser.add_argument("--service", default="frontend", help="Service to use with --latest")
    parser.add_argument("--limit", type=int, default=20, help="Search limit for --latest (default: 20)")
    args = parser.parse_args()

    if not args.latest and not args.trace_id:
        parser.error("trace_id is required unless --latest is used")

    try:
        trace_id = args.trace_id
        if args.latest:
            trace_id = fetch_latest_trace_id(args.jaeger_url, args.service, args.limit)
            print(f"latest_trace_id={trace_id}")
        payload = fetch_trace(args.jaeger_url, trace_id)
    except Exception as exc:
        print(f"Failed to fetch trace: {exc}", file=sys.stderr)
        return 1

    traces = payload.get("data", [])
    if not traces:
        print("No trace found.", file=sys.stderr)
        return 1

    trace = traces[0]
    spans = trace.get("spans", [])
    by_id = {span.get("spanID", ""): span for span in spans}
    children: dict[str, list[dict]] = defaultdict(list)
    roots: list[dict] = []

    for span in spans:
        refs = span.get("references", []) or []
        parent_id = ""
        for ref in refs:
            if ref.get("refType") == "CHILD_OF":
                parent_id = ref.get("spanID", "")
                break
        if parent_id and parent_id in by_id:
            children[parent_id].append(span)
        else:
            roots.append(span)

    roots.sort(key=lambda s: int(s.get("startTime", 0)))
    for child_list in children.values():
        child_list.sort(key=lambda s: int(s.get("startTime", 0)))

    print(f"trace_id={trace.get('traceID', trace_id)}")
    print(f"total_spans={len(spans)}")
    print(f"services={sorted({service_name_for_span(trace, s) for s in spans})}")
    print("call_tree:")
    for root in roots:
        print_span(trace, root, children)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
