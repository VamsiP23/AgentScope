#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Dict, List, Optional
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen


def prom_query(prom_url: str, query: str, timeout: int = 10) -> Dict[str, Any]:
    url = f"{prom_url.rstrip('/')}/api/v1/query?{urlencode({'query': query})}"
    with urlopen(url, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus query failed: {payload}")
    return payload.get("data", {})


def prom_scalar_optional(prom_url: str, query: str) -> Optional[float]:
    data = prom_query(prom_url, query)
    results = data.get("result", [])
    if not results:
        return None
    try:
        return float(results[0].get("value", [0, "0"])[1])
    except (TypeError, ValueError):
        return None


def jaeger_services(jaeger_url: str, timeout: int = 10) -> List[str]:
    with urlopen(f"{jaeger_url.rstrip('/')}/api/services", timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return list(payload.get("data", []) or [])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Validate telemetry sources required for AgentScope evidence collection.")
    p.add_argument("--prom-url", default="http://localhost:9090")
    p.add_argument("--jaeger-url", default="http://localhost:16686")
    p.add_argument("--namespace", default="default")
    p.add_argument("--require-services", default="frontend,checkoutservice")
    p.add_argument("--wait-seconds", type=int, default=30)
    p.add_argument("--poll-seconds", type=int, default=5)
    return p


def main() -> int:
    args = build_parser().parse_args()
    required_services = [item.strip() for item in args.require_services.split(",") if item.strip()]
    deadline = time.time() + max(1, args.wait_seconds)
    last_report: Dict[str, Any] = {}

    while True:
        checks: Dict[str, Dict[str, Any]] = {}
        failures: List[str] = []

        def add_check(name: str, ok: bool, value: Any = None, detail: str = "") -> None:
            checks[name] = {"ok": ok, "value": value, "detail": detail}
            if not ok:
                failures.append(name if not detail else f"{name}: {detail}")

        try:
            otel_up = prom_scalar_optional(args.prom_url, 'sum(up{job="otel-collector-spanmetrics"})')
            add_check("otel_spanmetrics_up", (otel_up or 0.0) >= 1.0, otel_up, "otel spanmetrics scrape target unavailable")
        except Exception as exc:
            add_check("otel_spanmetrics_up", False, None, str(exc))

        try:
            ksm_up = prom_scalar_optional(args.prom_url, 'sum(up{job="kube-state-metrics"})')
            add_check("kube_state_metrics_up", (ksm_up or 0.0) >= 1.0, ksm_up, "kube-state-metrics scrape target unavailable")
        except Exception as exc:
            add_check("kube_state_metrics_up", False, None, str(exc))

        try:
            cadvisor_up = prom_scalar_optional(args.prom_url, 'sum(up{job="kubernetes-cadvisor"})')
            add_check("cadvisor_up", (cadvisor_up or 0.0) >= 1.0, cadvisor_up, "cAdvisor scrape target unavailable")
        except Exception as exc:
            add_check("cadvisor_up", False, None, str(exc))

        try:
            cpu_series = prom_scalar_optional(
                args.prom_url,
                f'count(container_cpu_usage_seconds_total{{namespace="{args.namespace}",pod!=""}})',
            )
            add_check("cpu_series_present", (cpu_series or 0.0) > 0.0, cpu_series, "container CPU series missing")
        except Exception as exc:
            add_check("cpu_series_present", False, None, str(exc))

        try:
            mem_series = prom_scalar_optional(
                args.prom_url,
                f'count(container_memory_working_set_bytes{{namespace="{args.namespace}",pod!=""}})',
            )
            add_check("memory_series_present", (mem_series or 0.0) > 0.0, mem_series, "container memory series missing")
        except Exception as exc:
            add_check("memory_series_present", False, None, str(exc))

        try:
            limit_series = prom_scalar_optional(
                args.prom_url,
                f'count(kube_pod_container_resource_limits{{namespace="{args.namespace}",resource="cpu"}})',
            )
            add_check("cpu_limit_series_present", (limit_series or 0.0) > 0.0, limit_series, "CPU limit series missing")
        except Exception as exc:
            add_check("cpu_limit_series_present", False, None, str(exc))

        try:
            request_series = prom_scalar_optional(
                args.prom_url,
                f'count(kube_pod_container_resource_requests{{namespace="{args.namespace}",resource="memory"}})',
            )
            add_check("memory_request_series_present", (request_series or 0.0) > 0.0, request_series, "memory request series missing")
        except Exception as exc:
            add_check("memory_request_series_present", False, None, str(exc))

        try:
            services = jaeger_services(args.jaeger_url)
            missing = [svc for svc in required_services if svc not in services]
            add_check("jaeger_services", not missing, services[:20], f"missing services in Jaeger: {', '.join(missing)}" if missing else "")
        except (URLError, RuntimeError, TimeoutError) as exc:
            add_check("jaeger_services", False, None, str(exc))
        except Exception as exc:
            add_check("jaeger_services", False, None, str(exc))

        last_report = {
            "checked_at_epoch": time.time(),
            "checks": checks,
            "ok": not failures,
            "failures": failures,
        }

        if not failures:
            print(json.dumps(last_report, indent=2))
            return 0

        if time.time() >= deadline:
            print(json.dumps(last_report, indent=2))
            return 1

        time.sleep(max(1, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
