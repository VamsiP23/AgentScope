from __future__ import annotations

from typing import Any, Dict, List

from agent_graph.react_support import BAD_ROLLOUT_MARKERS, collect_output_text, extract_markers, metrics_signal_summary


def truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)] + "..."


def format_thought(decision: Dict[str, Any]) -> str:
    belief = str(decision.get("belief", "")).strip()
    uncertainty = str(decision.get("uncertainty", "")).strip()
    next_evidence = str(decision.get("next_evidence_needed", "")).strip()
    parts = [f"Belief: {belief}"]
    leading = str(decision.get("leading_hypothesis", "")).strip()
    alternative = str(decision.get("alternative_hypothesis", "")).strip()
    support = str(decision.get("evidence_supporting_leading", "")).strip()
    mind_change = str(decision.get("what_result_would_change_my_mind", "")).strip()
    impact = str(decision.get("decision_impact", "")).strip()
    why = str(decision.get("why_this_tool_reduces_uncertainty", "")).strip()
    if leading:
        parts.append(f"Hypotheses: {leading} vs {alternative}" if alternative else f"Hypothesis: {leading}")
    if support:
        parts.append(f"Support: {support}")
    parts.append(f"Uncertainty: {uncertainty}")
    parts.append(f"Next evidence: {next_evidence}")
    if impact:
        parts.append(f"Decision impact: {impact}")
    if mind_change:
        parts.append(f"Would change my mind if: {mind_change}")
    if why:
        parts.append(f"Why: {why}")
    return " | ".join(parts)


def summarize_output_for_prompt(output: Dict[str, Any]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    scalar_keys = [
        "service",
        "entry_point",
        "entry_service",
        "trace_count",
        "focus_trace_count",
        "raw_trace_count",
        "application_trace_count",
        "bottleneck_service",
        "bottleneck_pct_of_total",
        "deviation_factor",
        "summary",
        "error_count",
        "pod_name",
        "desired_replicas",
        "available_replicas",
        "rollout_progressing",
        "restart_count",
        "exit_code",
        "solution_logged",
        "root_cause",
        "action_taken",
        "evidence_valid",
    ]
    for key in scalar_keys:
        if key in output:
            summary[key] = output.get(key)

    error_value = output.get("error")
    if error_value:
        summary["error"] = truncate(str(error_value), 160)

    recent_events = output.get("recent_events", []) or []
    if recent_events:
        ranked_events = sorted(
            recent_events,
            key=lambda item: (
                0 if str((item or {}).get("type", "")).lower() == "warning" else 1,
                0 if "fail" in str((item or {}).get("reason", "")).lower() else 1,
                0 if "backoff" in str((item or {}).get("reason", "")).lower() else 1,
            ),
        )
        summary["recent_events"] = [
            {
                "reason": str(item.get("reason", "")),
                "object": str(item.get("object", "")),
                "type": str(item.get("type", "")),
                "message": truncate(str(item.get("message", "")), 120),
            }
            for item in ranked_events[:4]
        ]

    pod_phases = output.get("pod_phases", []) or []
    if pod_phases:
        summary["pod_phases"] = [
            {
                "pod_name": str(item.get("pod_name", "")),
                "phase": str(item.get("phase", "")),
                "ready": bool(item.get("ready", False)),
                "restart_count": int(item.get("restart_count", 0) or 0),
            }
            for item in pod_phases[:3]
        ]
    if "desired_replicas" in output or "available_replicas" in output:
        desired = int(output.get("desired_replicas", 0) or 0)
        available = int(output.get("available_replicas", 0) or 0)
        summary["availability_gap"] = f"{available}/{desired}"

    startup_markers = extract_markers(collect_output_text(output).lower(), BAD_ROLLOUT_MARKERS)
    if startup_markers:
        summary["startup_failure_markers"] = startup_markers[:4]

    metrics = output.get("metrics", {}) or {}
    if metrics:
        summary["metrics"] = {
            "cpu_usage": metrics.get("cpu_usage", 0.0),
            "cpu_utilization_pct_of_limit": metrics.get("cpu_utilization_pct_of_limit", 0.0),
            "cpu_throttling_ratio": metrics.get("cpu_throttling_ratio", 0.0),
            "memory_usage": metrics.get("memory_usage", 0.0),
            "memory_utilization_pct_of_limit": metrics.get("memory_utilization_pct_of_limit", 0.0),
            "error_rate": metrics.get("error_rate", 0.0),
            "p95_latency_ms": metrics.get("p95_latency_ms", 0.0),
            "p99_latency_ms": metrics.get("p99_latency_ms", 0.0),
            "resource_metrics_available": metrics.get("resource_metrics_available", False),
            "application_metrics_available": metrics.get("application_metrics_available", False),
        }
        gaps = list(metrics.get("resource_metric_gaps", []) or [])
        if gaps:
            summary["resource_metric_gaps"] = gaps[:6]
        summary["metrics_signal"] = metrics_signal_summary(metrics)

    if "trace_count" in output:
        trace_count = int(output.get("trace_count", 0) or 0)
        if output.get("error") or bool(output.get("observability_error", False)) or str(output.get("trace_quality", "")).strip() == "unavailable":
            summary["trace_signal"] = "trace data unavailable from Jaeger"
            summary["observability_takeaway"] = "trace query failed; do not infer service failure from trace retrieval failure alone"
        elif trace_count <= 0:
            summary["trace_signal"] = "no traces returned in the current lookback window"
        else:
            bottleneck = str(output.get("bottleneck_service", "")).strip()
            if bottleneck:
                pct = float(output.get("bottleneck_pct_of_total", 0.0) or 0.0)
                summary["trace_signal"] = f"bottleneck={bottleneck} pct={pct:.2f}"

    downstream_candidates = output.get("downstream_candidates", []) or []
    if downstream_candidates:
        summary["downstream_candidates"] = [
            {
                "service": str(item.get("service", "")),
                "avg_duration_ms": float(item.get("avg_duration_ms", 0.0) or 0.0),
                "avg_pct_of_total": float(item.get("avg_pct_of_total", 0.0) or 0.0),
                "count": int(item.get("count", 0) or 0),
            }
            for item in downstream_candidates[:3]
        ]
        top = downstream_candidates[0]
        summary["dependency_trace_signal"] = (
            f"entry={str(output.get('entry_service', 'frontend'))} "
            f"target={str(output.get('service', ''))} "
            f"downstream_bottleneck={str(top.get('service', ''))} "
            f"pct={float(top.get('avg_pct_of_total', 0.0) or 0.0):.2f}"
        )

    return summary


def summarize_output(output: Dict[str, Any]) -> Dict[str, Any]:
    summary = summarize_output_for_prompt(output)
    if "call_chain" in output:
        summary["call_chain_hops"] = len(output.get("call_chain", []) or [])
    if "error_spans" in output:
        summary["error_span_count"] = len(output.get("error_spans", []) or [])
    if "recent_events" in output:
        summary["recent_event_count"] = len(output.get("recent_events", []) or [])
    if "pod_phases" in output:
        summary["pod_count"] = len(output.get("pod_phases", []) or [])
    return summary


def tool_signatures(allowed_tools: List[str]) -> Dict[str, str]:
    signatures = {
        "get_metrics": "get_metrics(service, lookback_minutes=5) -> {call_id, timestamp, service, metrics:{cpu_usage,cpu_mcores,cpu_request_cores,cpu_limit_cores,cpu_utilization_pct_of_request,cpu_utilization_pct_of_limit,cpu_throttled_seconds_rate,cpu_throttling_ratio,memory_usage,memory_rss_bytes,memory_request_bytes,memory_limit_bytes,memory_utilization_pct_of_request,memory_utilization_pct_of_limit,error_rate,p95_latency_ms,p99_latency_ms,request_rps,error_rps,resource_metrics_available,application_metrics_available,resource_metric_gaps,application_metric_gaps}, error}",
        "get_traces": "get_traces(service, lookback_minutes=5) -> {call_id, timestamp, entry_point, call_chain, bottleneck_service, bottleneck_pct_of_total, error_spans, deviation_factor, error}",
        "get_dependency_traces": "get_dependency_traces(service, entry_service='frontend', lookback_minutes=5) -> {call_id, timestamp, service, entry_service, downstream_candidates, bottleneck_service, bottleneck_pct_of_total, trace_count, error}",
        "get_logs": "get_logs(service, tail_lines=100) -> {call_id, timestamp, pod_name, error_count, error_lines, signal_lines, recent_lines, pods:[{pod_name,error_count,error_lines,signal_lines,recent_lines}], error}",
        "get_k8s_state": "get_k8s_state(service) -> {call_id, timestamp, desired_replicas, available_replicas, pod_phases, recent_events, rollout_progressing, restart_count, error}",
        "restart_pod": "restart_pod(service, pod_name='') -> {call_id, timestamp, service, pod_name, executed, command, result, error}",
        "rollout_restart": "rollout_restart(service) -> {call_id, timestamp, service, executed, command, result, error}",
        "rollout_undo": "rollout_undo(service) -> {call_id, timestamp, service, executed, command, result, error}",
        "patch_resources": "patch_resources(service, cpu_request='', cpu_limit='', memory_request='', memory_limit='', container='server') -> {call_id, timestamp, service, executed, command, result, error}",
        "wait_and_monitor": "wait_and_monitor(seconds=30) -> {call_id, timestamp, executed, command, result, error}",
        "exec_shell": "exec_shell(command) -> {call_id, timestamp, stdout, stderr, exit_code, rejected, error}",
        "submit_solution": "submit_solution(root_cause, action_taken, confidence, evidence) -> {call_id, timestamp, solution_logged, evidence_valid, invalid_evidence, error}",
    }
    return {tool: signatures[tool] for tool in allowed_tools}
