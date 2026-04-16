from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def metrics_output(service: str, metrics: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "service": service,
        "metrics": {
            "cpu_usage": metrics.get("cpu_cores", 0.0),
            "cpu_mcores": metrics.get("cpu_mcores", 0.0),
            "cpu_request_cores": metrics.get("cpu_request_cores", 0.0),
            "cpu_limit_cores": metrics.get("cpu_limit_cores", 0.0),
            "cpu_utilization_pct_of_request": metrics.get("cpu_utilization_pct_of_request", 0.0),
            "cpu_utilization_pct_of_limit": metrics.get("cpu_utilization_pct_of_limit", 0.0),
            "cpu_headroom_cores_to_limit": metrics.get("cpu_headroom_cores_to_limit", 0.0),
            "cpu_throttled_seconds_rate": metrics.get("cpu_throttled_seconds_rate", 0.0),
            "cpu_throttled_periods_rate": metrics.get("cpu_throttled_periods_rate", 0.0),
            "cpu_periods_rate": metrics.get("cpu_periods_rate", 0.0),
            "cpu_throttling_ratio": metrics.get("cpu_throttling_ratio", 0.0),
            "memory_usage": metrics.get("memory_bytes", 0.0),
            "memory_rss_bytes": metrics.get("memory_rss_bytes", 0.0),
            "error_rate": metrics.get("error_rate", 0.0),
            "p95_latency_ms": metrics.get("latency_p95_ms", 0.0),
            "p99_latency_ms": metrics.get("latency_p99_ms", 0.0),
            "request_rps": metrics.get("request_rps", 0.0),
            "error_rps": metrics.get("error_rps", 0.0),
            "memory_mib": metrics.get("memory_mib", 0.0),
            "memory_rss_mib": metrics.get("memory_rss_mib", 0.0),
            "memory_request_bytes": metrics.get("memory_request_bytes", 0.0),
            "memory_limit_bytes": metrics.get("memory_limit_bytes", 0.0),
            "memory_request_mib": metrics.get("memory_request_mib", 0.0),
            "memory_limit_mib": metrics.get("memory_limit_mib", 0.0),
            "memory_utilization_pct_of_request": metrics.get("memory_utilization_pct_of_request", 0.0),
            "memory_utilization_pct_of_limit": metrics.get("memory_utilization_pct_of_limit", 0.0),
            "memory_headroom_bytes_to_limit": metrics.get("memory_headroom_bytes_to_limit", 0.0),
            "resource_metrics_available": metrics.get("resource_metrics_available", False),
            "application_metrics_available": metrics.get("application_metrics_available", False),
            "resource_metric_gaps": metrics.get("resource_metric_gaps", []) or [],
            "application_metric_gaps": metrics.get("application_metric_gaps", []) or [],
        },
        "error": metrics.get("error"),
    }


def trace_summary_output(service: str, summary: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "service": service,
        "entry_point": summary.get("entry_point", service),
        "trace_count": summary.get("trace_count", 0),
        "call_chain": summary.get("call_chain", []) or [],
        "bottleneck_service": summary.get("bottleneck_service", ""),
        "bottleneck_pct_of_total": summary.get("bottleneck_pct_of_total", 0.0),
        "error_spans": summary.get("error_spans", []) or [],
        "deviation_factor": summary.get("deviation_factor", 0.0),
        "baseline_p99_ms": summary.get("baseline_p99_ms", 0.0),
        "slowest_trace_id": summary.get("slowest_trace_id", ""),
        "trace_quality": summary.get("trace_quality", "missing"),
        "observability_error": bool(summary.get("observability_error", False)),
        "observability_status": str(summary.get("observability_status", "")),
        "error": summary.get("error"),
    }


def dependency_trace_output(service: str, entry_service: str, summary: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "service": service,
        "entry_service": summary.get("entry_service", entry_service),
        "trace_count": summary.get("trace_count", 0),
        "focus_trace_count": summary.get("focus_trace_count", 0),
        "raw_trace_count": summary.get("raw_trace_count", 0),
        "application_trace_count": summary.get("application_trace_count", 0),
        "call_chain": summary.get("call_chain", []) or [],
        "downstream_candidates": summary.get("downstream_candidates", []) or [],
        "bottleneck_service": summary.get("bottleneck_service", ""),
        "bottleneck_pct_of_total": summary.get("bottleneck_pct_of_total", 0.0),
        "error_spans": summary.get("error_spans", []) or [],
        "trace_quality": summary.get("trace_quality", "missing"),
        "observability_error": bool(summary.get("observability_error", False)),
        "observability_status": str(summary.get("observability_status", "")),
        "summary": str(summary.get("summary", "")),
        "error": summary.get("error"),
    }


def trace_detail_output(trace_id: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "trace_id": trace_id,
        "service": detail.get("service", ""),
        "total_duration_ms": detail.get("total_duration_ms", 0.0),
        "has_error": detail.get("has_error", False),
        "error_types": detail.get("error_types", []) or [],
        "hops": detail.get("hops", []) or [],
        "error": detail.get("error"),
    }


def validate_solution_payload(
    run_log: List[Dict[str, Any]],
    root_cause: str,
    action_taken: str,
    confidence: float,
    evidence: List[str],
    fault_class: str = "",
    affected_service: str = "",
    action_type: str = "",
) -> Dict[str, Any]:
    normalized_root_cause = str(root_cause).strip()
    normalized_action = str(action_taken).strip()
    normalized_fault_class = str(fault_class).strip()
    normalized_affected_service = str(affected_service).strip()
    normalized_action_type = str(action_type).strip()
    valid_call_ids = {
        record["call_id"]
        for record in run_log
        if record.get("method") != "submit_solution"
    }
    invalid_evidence = [call_id for call_id in evidence if call_id not in valid_call_ids]
    validation_errors: List[str] = []
    if not normalized_root_cause:
        validation_errors.append("root_cause is required")
    if not normalized_action:
        validation_errors.append("action_taken is required")
    if not evidence:
        validation_errors.append("at least one evidence call_id is required")
    if invalid_evidence:
        validation_errors.append("solution cited non-existent tool call IDs")
    return {
        "solution_logged": len(validation_errors) == 0,
        "root_cause": normalized_root_cause,
        "action_taken": normalized_action,
        "fault_class": normalized_fault_class,
        "affected_service": normalized_affected_service,
        "action_type": normalized_action_type,
        "confidence": float(confidence),
        "evidence": list(evidence),
        "evidence_valid": len(invalid_evidence) == 0,
        "invalid_evidence": invalid_evidence,
        "error": None if not validation_errors else "; ".join(validation_errors),
    }


def action_output(service: str, dry_run: bool, result: Dict[str, Any], *, pod_name: str = "") -> Dict[str, Any]:
    output = {
        "service": service,
        "pod_name": pod_name,
        "dry_run": dry_run,
        "executed": bool(result.get("executed", False)),
        "command": result.get("command", []),
        "result": result.get("result"),
        "error": None,
    }
    raw_result = result.get("result")
    if isinstance(raw_result, dict):
        stderr = str(raw_result.get("stderr", "") or "")
        stdout = str(raw_result.get("stdout", "") or "")
        returncode = int(raw_result.get("returncode", 0) or 0)
        output["exit_code"] = returncode
        output["stdout"] = stdout
        output["stderr"] = stderr
        if returncode != 0:
            output["error"] = stderr or stdout or "action failed"
    return output


def build_call_record(method: str, inputs: Dict[str, Any], output: Dict[str, Any]) -> Dict[str, Any]:
    call_id = output["call_id"]
    timestamp = output["timestamp"]
    return {
        "call_id": call_id,
        "timestamp": timestamp,
        "method": method,
        "inputs": inputs,
        "outputs": output,
    }


def append_jsonl_record(path: Any, record: Dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")
