from __future__ import annotations

import json
from collections import Counter
from typing import Any, Dict, List
from urllib.parse import urlencode
from urllib.request import urlopen


class JaegerTools:
    def __init__(self, jaeger_url: str) -> None:
        self.jaeger_url = jaeger_url.rstrip("/")

    def _fetch_json(self, url: str) -> Dict[str, Any]:
        with urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def latest_application_trace(self, service: str, limit: int = 20) -> Dict[str, Any]:
        params = urlencode({"service": service, "limit": limit, "lookback": "1h"})
        payload = self._fetch_json(f"{self.jaeger_url}/api/traces?{params}")
        traces = payload.get("data", [])
        for trace in traces:
            spans = trace.get("spans", [])
            names = {span.get("operationName", "") for span in spans}
            if any("TraceService/Export" in name for name in names):
                continue
            return self.summarize_trace(trace)
        return {
            "trace_found": False,
            "service": service,
            "summary": f"no application traces found for {service}",
        }

    def summarize_trace(self, trace: Dict[str, Any]) -> Dict[str, Any]:
        spans = trace.get("spans", [])
        processes = trace.get("processes", {})
        services = []
        error_spans = []
        durations = []
        for span in spans:
            process_id = span.get("processID", "")
            service_name = processes.get(process_id, {}).get("serviceName", "unknown")
            services.append(service_name)
            durations.append(int(span.get("duration", 0)))
            status = self._span_status(span)
            if status not in {"ok", "200", "0"}:
                error_spans.append(
                    {
                        "service": service_name,
                        "operation": span.get("operationName", "unknown"),
                        "status": status,
                    }
                )
        service_counts = Counter(services)
        return {
            "trace_found": True,
            "trace_id": trace.get("traceID", ""),
            "total_spans": len(spans),
            "services": sorted(service_counts.keys()),
            "service_span_counts": dict(service_counts),
            "max_span_ms": round((max(durations) / 1000.0), 3) if durations else 0.0,
            "error_spans": error_spans[:10],
            "summary": (
                f"trace spans={len(spans)} services={sorted(service_counts.keys())} "
                f"error_spans={len(error_spans)}"
            ),
        }

    def _span_status(self, span: Dict[str, Any]) -> str:
        for tag in span.get("tags", []) or []:
            if tag.get("key") in {"rpc.grpc.status_code", "http.status_code"}:
                return str(tag.get("value", "ok"))
        return "ok"
