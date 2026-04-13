from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional


def observability_error_message(exc: Exception | None) -> str:
    detail = str(exc) if exc is not None else "unknown Jaeger error"
    return f"trace data unavailable from Jaeger: {detail}"


def duration_ms(duration_microseconds: Any) -> float:
    try:
        return float(duration_microseconds) / 1000.0
    except Exception:
        return 0.0


def percentile(values: List[float], target_percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, round((target_percentile / 100.0) * (len(ordered) - 1))))
    return float(ordered[rank])


def service_name(processes: Dict[str, Any], process_id: str) -> str:
    process = dict(processes.get(process_id, {}) or {})
    return str(process.get("serviceName", ""))


def normalize_service_name(service: str) -> str:
    return str(service or "").strip().lower()


def normalize_dependency_name(peer_service: str) -> str:
    value = str(peer_service or "").strip()
    if not value:
        return ""
    value = value.split("/", 1)[0]
    value = value.split(".")[-1]
    return "".join(ch for ch in value.lower() if ch.isalnum() or ch == "-")


def root_span(spans: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    span_ids = {str(span.get("spanID", "")) for span in spans}
    for span in spans:
        refs = span.get("references", []) or []
        if not refs:
            return span
        parent_ids = {str(ref.get("spanID", "")) for ref in refs if str(ref.get("refType", "")) == "CHILD_OF"}
        if not parent_ids.intersection(span_ids):
            return span
    return spans[0] if spans else None


def is_probe_or_health_trace(trace: Dict[str, Any]) -> bool:
    spans = list(trace.get("spans", []) or [])
    if not spans:
        return True
    meaningful_spans = 0
    for span in spans:
        tags = {str(tag.get("key", "")): str(tag.get("value", "")) for tag in span.get("tags", []) or []}
        user_agent = tags.get("user_agent.original", "").lower()
        http_target = tags.get("http.target", "")
        operation = str(span.get("operationName", "")).lower()
        if "kube-probe" in user_agent:
            continue
        if http_target == "/_healthz":
            continue
        if "grpc.health" in operation or "healthcheck" in operation:
            continue
        if "traceservice/export" in operation:
            continue
        meaningful_spans += 1
    return meaningful_spans == 0


def span_has_error(span: Dict[str, Any]) -> bool:
    for tag in span.get("tags", []) or []:
        key = str(tag.get("key", ""))
        value = str(tag.get("value", "")).lower()
        if key == "error" and value in {"true", "1"}:
            return True
        if key in {"otel.status_code", "status.code"} and value == "error":
            return True
    return False


def span_error_message(span: Dict[str, Any]) -> str:
    for key in ("error.message", "otel.status_description", "rpc.grpc.status_code", "http.status_code"):
        for tag in span.get("tags", []) or []:
            if str(tag.get("key", "")) == key:
                value = str(tag.get("value", "")).strip()
                if value:
                    return value
    return ""


def span_peer_service(span: Dict[str, Any]) -> str:
    for key in ("peer.service", "rpc.service", "net.peer.name", "db.system"):
        for tag in span.get("tags", []) or []:
            if str(tag.get("key", "")) == key:
                value = str(tag.get("value", "")).strip()
                if value:
                    return value
    return ""


def parse_trace(trace: Dict[str, Any]) -> Dict[str, Any]:
    spans = list(trace.get("spans", []) or [])
    processes = dict(trace.get("processes", {}) or {})
    root = root_span(spans)
    total_duration = duration_ms(root.get("duration", 0) if root else 0)
    if spans:
        total_duration = max(total_duration, max(duration_ms(span.get("duration", 0)) for span in spans))

    hops: List[Dict[str, Any]] = []
    error_types: List[str] = []
    for span in sorted(spans, key=lambda item: int(item.get("startTime", 0))):
        hop_service = service_name(processes, span.get("processID", ""))
        hop_duration = duration_ms(span.get("duration", 0))
        error = span_has_error(span)
        error_message = span_error_message(span)
        peer_service = span_peer_service(span)
        if error and error_message:
            error_types.append(error_message)
        hop = {
            "span_id": span.get("spanID", ""),
            "service": hop_service,
            "operation": span.get("operationName", ""),
            "duration_ms": hop_duration,
            "pct_of_total": min((hop_duration / total_duration), 1.0) if total_duration > 0 else 0.0,
            "error": error,
            "error_message": error_message,
        }
        if peer_service:
            hop["peer_service"] = peer_service
        hops.append(hop)

    return {
        "trace_id": trace.get("traceID", ""),
        "service": service_name(processes, root.get("processID", "")) if root else "",
        "total_duration_ms": total_duration,
        "has_error": any(hop["error"] for hop in hops),
        "error_types": sorted({item for item in error_types if item}),
        "hops": hops,
    }


def find_common_bottleneck(traces: List[Dict[str, Any]]) -> Dict[str, Any]:
    service_totals: Dict[str, List[float]] = {}
    for trace in traces:
        total = trace["total_duration_ms"]
        for hop in trace["hops"]:
            service = hop["service"]
            if not service or service == trace["service"]:
                continue
            service_totals.setdefault(service, []).append(hop["duration_ms"] / total if total > 0 else 0.0)
    if not service_totals:
        return {}

    best_service = max(service_totals.items(), key=lambda item: sum(item[1]) / len(item[1]))[0]
    ratios = service_totals[best_service]
    durations = [
        hop["duration_ms"]
        for trace in traces
        for hop in trace["hops"]
        if hop["service"] == best_service
    ]
    return {
        "service": best_service,
        "avg_duration_ms": (sum(durations) / len(durations)) if durations else 0.0,
        "pct_of_total": sum(ratios) / len(ratios),
    }


def extract_error_types(traces: List[Dict[str, Any]]) -> List[str]:
    counts: Counter[str] = Counter()
    for trace in traces:
        for item in trace["error_types"]:
            counts[item] += 1
    return [name for name, _ in counts.most_common(5)]


def classify_health(has_errors: bool, has_slowness: bool, has_data: bool) -> str:
    if not has_data:
        return "unknown"
    if has_errors and has_slowness:
        return "both"
    if has_errors:
        return "erroring"
    if has_slowness:
        return "slow"
    return "healthy"


def trace_has_invalid_percentages(trace: Dict[str, Any]) -> bool:
    for hop in trace.get("hops", []) or []:
        pct = float(hop.get("pct_of_total", 0.0) or 0.0)
        if pct < 0.0 or pct > 1.0:
            return True
    return False


def trace_quality(application_traces: List[Dict[str, Any]], raw_traces: List[Dict[str, Any]]) -> str:
    if not raw_traces:
        return "missing"
    if not application_traces:
        return "weak"
    if any(trace_has_invalid_percentages(trace) for trace in application_traces):
        return "weak"
    return "good"


def dependency_trace_quality(
    raw_traces: List[Dict[str, Any]],
    application_traces: List[Dict[str, Any]],
    relevant_traces: List[Dict[str, Any]],
    downstream_candidates: List[Dict[str, Any]],
) -> str:
    if not raw_traces:
        return "missing"
    if not application_traces or not relevant_traces or not downstream_candidates:
        return "weak"
    if any(trace_has_invalid_percentages(trace) for trace in relevant_traces):
        return "weak"
    return "good"


def trace_contains_service(trace: Dict[str, Any], service: str) -> bool:
    normalized = normalize_service_name(service)
    for hop in trace.get("hops", []) or []:
        if normalize_service_name(str(hop.get("service", ""))) == normalized:
            return True
    return normalize_service_name(str(trace.get("service", ""))) == normalized


def focus_service_path(trace: Dict[str, Any], service: str) -> List[Dict[str, Any]]:
    if not trace:
        return []
    normalized = normalize_service_name(service)
    focus_hops: List[Dict[str, Any]] = []
    for hop in trace.get("hops", []) or []:
        if normalize_service_name(str(hop.get("service", ""))) != normalized:
            continue
        focus_hops.append(
            {
                "service": normalized,
                "downstream_service": normalize_dependency_name(str(hop.get("peer_service", ""))),
                "operation": str(hop.get("operation", "")),
                "duration_ms": float(hop.get("duration_ms", 0.0) or 0.0),
                "pct_of_total": float(hop.get("pct_of_total", 0.0) or 0.0),
                "error": bool(hop.get("error", False)),
                "error_message": str(hop.get("error_message", "")),
            }
        )
    return focus_hops[:8]


def entry_point_summary(service: str, traces: List[Dict[str, Any]], bottleneck: Dict[str, Any]) -> str:
    if not traces:
        return f"no application traces found for {service}"
    if bottleneck:
        return (
            f"{service} traces point to {bottleneck['service']} as the common bottleneck "
            f"at {bottleneck['pct_of_total'] * 100:.1f}% of total latency"
        )
    return f"{service} has {len(traces)} application traces but no repeated downstream bottleneck"


def dependency_trace_summary_text(
    service: str,
    entry_service: str,
    relevant_trace_count: int,
    downstream_candidates: List[Dict[str, Any]],
) -> str:
    if relevant_trace_count <= 0:
        return f"no {entry_service} traces in the current window showed downstream calls from {service}"
    if not downstream_candidates:
        return f"{entry_service} traces include {service}, but no repeated downstream bottleneck was identified beneath it"
    top = downstream_candidates[0]
    return (
        f"{entry_service} traces flowing through {service} most often bottleneck on {top['service']} "
        f"at {float(top.get('avg_pct_of_total', 0.0) or 0.0) * 100:.1f}% of total latency"
    )


def dependency_health_summary(
    service: str,
    total: int,
    error_traces: List[Dict[str, Any]],
    slow_traces: List[Dict[str, Any]],
    error_types: List[str],
) -> str:
    if total == 0:
        return f"no application traces found for {service}"
    classification = classify_health(bool(error_traces), bool(slow_traces), total > 0)
    top_error = error_types[0] if error_types else "none"
    return f"{service} classified as {classification}; errors={len(error_traces)}/{total}, slow={len(slow_traces)}/{total}, top_error={top_error}"
