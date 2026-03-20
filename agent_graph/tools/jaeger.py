from __future__ import annotations

import json
from collections import Counter
from typing import Any, Dict, List, Tuple
from urllib.parse import urlencode
from urllib.request import urlopen


class JaegerTools:
    def __init__(self, jaeger_url: str) -> None:
        self.jaeger_url = jaeger_url.rstrip("/")

    def _fetch_json(self, url: str) -> Dict[str, Any]:
        with urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _search_traces(self, service: str, *, limit: int = 20, lookback: str = "1h") -> List[Dict[str, Any]]:
        params = urlencode({"service": service, "limit": limit, "lookback": lookback})
        payload = self._fetch_json(f"{self.jaeger_url}/api/traces?{params}")
        return payload.get("data", [])

    def _process_service_name(self, trace: Dict[str, Any], span: Dict[str, Any]) -> str:
        process_id = span.get("processID", "")
        return trace.get("processes", {}).get(process_id, {}).get("serviceName", "unknown")

    def _span_status(self, span: Dict[str, Any]) -> str:
        error = False
        status = "ok"
        for tag in span.get("tags", []) or []:
            key = str(tag.get("key", ""))
            value = tag.get("value", "")
            if key == "error" and value is True:
                error = True
            if key in {"rpc.grpc.status_code", "http.status_code"}:
                status = str(value)
        if error and status == "ok":
            return "error"
        return status

    def _span_peer(self, span: Dict[str, Any]) -> str:
        peer = ""
        for tag in span.get("tags", []) or []:
            key = str(tag.get("key", ""))
            if key in {"net.peer.name", "peer.service"}:
                peer = str(tag.get("value", ""))
                if peer:
                    return peer
        return peer

    def _references_parent(self, span: Dict[str, Any]) -> str:
        refs = span.get("references", []) or []
        for ref in refs:
            if ref.get("refType") == "CHILD_OF":
                return str(ref.get("spanID", ""))
        return ""

    def summarize_trace(self, trace: Dict[str, Any]) -> Dict[str, Any]:
        spans = trace.get("spans", []) or []
        spans_by_id = {span.get("spanID", ""): span for span in spans}
        services = Counter()
        error_spans: List[Dict[str, Any]] = []
        durations: List[int] = []
        downstream_failures: List[Dict[str, Any]] = []

        for span in spans:
            service_name = self._process_service_name(trace, span)
            services[service_name] += 1
            durations.append(int(span.get("duration", 0)))

            status = self._span_status(span)
            if status not in {"ok", "200", "0"}:
                parent_id = self._references_parent(span)
                parent_service = self._process_service_name(trace, spans_by_id[parent_id]) if parent_id and parent_id in spans_by_id else ""
                peer = self._span_peer(span)
                error_span = {
                    "service": service_name,
                    "operation": span.get("operationName", "unknown"),
                    "status": status,
                    "peer": peer,
                    "parent_service": parent_service,
                    "duration_ms": round(int(span.get("duration", 0)) / 1000.0, 3),
                }
                error_spans.append(error_span)
                caller = parent_service or service_name
                callee = peer or service_name
                # Ignore root/self failures when summarizing downstream failures.
                # They are useful as error spans, but they are not evidence of a failing hop.
                if peer and caller != callee:
                    downstream_failures.append(
                        {
                            "caller": caller,
                            "callee": callee,
                            "status": status,
                        }
                    )

        return {
            "trace_found": True,
            "trace_id": trace.get("traceID", ""),
            "total_spans": len(spans),
            "services": sorted(services.keys()),
            "service_span_counts": dict(services),
            "max_span_ms": round((max(durations) / 1000.0), 3) if durations else 0.0,
            "error_spans": error_spans[:10],
            "downstream_failures": downstream_failures[:10],
            "summary": (
                f"trace spans={len(spans)} services={sorted(services.keys())} "
                f"error_spans={len(error_spans)}"
            ),
        }

    def recent_failing_traces(self, service: str, *, limit: int = 10, lookback: str = "1h") -> Dict[str, Any]:
        traces = self._search_traces(service, limit=limit, lookback=lookback)
        summaries: List[Dict[str, Any]] = []
        for trace in traces:
            summary = self.summarize_trace(trace)
            if summary.get("error_spans"):
                summaries.append(summary)
        if not summaries:
            return {
                "trace_found": False,
                "service": service,
                "trace_count": 0,
                "failing_traces": [],
                "summary": f"no failing application traces found for {service}",
            }
        return {
            "trace_found": True,
            "service": service,
            "trace_count": len(summaries),
            "failing_traces": summaries,
            "summary": f"found {len(summaries)} failing traces for {service}",
        }

    def failing_downstream_summary(self, service: str, *, limit: int = 10, lookback: str = "1h") -> Dict[str, Any]:
        failing = self.recent_failing_traces(service, limit=limit, lookback=lookback)
        if not failing.get("trace_found", False):
            return {
                "trace_found": False,
                "service": service,
                "downstream_counts": [],
                "summary": f"no downstream failures found for {service}",
            }

        downstream_counter: Counter[Tuple[str, str]] = Counter()
        status_counter: Counter[str] = Counter()
        examples: List[Dict[str, Any]] = []

        for trace in failing.get("failing_traces", []):
            for failure in trace.get("downstream_failures", []):
                callee = str(failure.get("callee", "unknown"))
                caller = str(failure.get("caller", service))
                status = str(failure.get("status", "error"))
                downstream_counter[(caller, callee)] += 1
                status_counter[status] += 1
                if len(examples) < 5:
                    examples.append(
                        {
                            "trace_id": trace.get("trace_id", ""),
                            "caller": caller,
                            "callee": callee,
                            "status": status,
                        }
                    )

        counts = [
            {
                "caller": caller,
                "callee": callee,
                "count": count,
            }
            for (caller, callee), count in downstream_counter.most_common(10)
        ]

        top = counts[0] if counts else None
        summary = (
            f"most common failing downstream from {service}: {top['caller']} -> {top['callee']} ({top['count']} traces)"
            if top
            else f"no downstream failures found for {service}"
        )
        return {
            "trace_found": bool(counts),
            "service": service,
            "downstream_counts": counts,
            "status_counts": dict(status_counter),
            "examples": examples,
            "summary": summary,
        }

    def latest_application_trace(self, service: str, limit: int = 20) -> Dict[str, Any]:
        traces = self._search_traces(service, limit=limit, lookback="1h")
        for trace in traces:
            summary = self.summarize_trace(trace)
            names = {item.get("operation", "") for item in summary.get("error_spans", [])}
            if any("TraceService/Export" in name for name in names):
                continue
            return summary
        return {
            "trace_found": False,
            "service": service,
            "summary": f"no application traces found for {service}",
        }
