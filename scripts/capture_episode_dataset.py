#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarking.episode import (
    BenchmarkEpisode,
    EpisodeGroundTruth,
    EpisodePhase,
    EpisodeProvenance,
    EpisodeScoring,
    EpisodeTelemetryContract,
    EpisodeTransition,
)
from benchmarking.problem import load_benchmark_suite


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def signal_class_for_line(line: str) -> str:
    lowered = line.lower()
    if "deadline exceeded" in lowered or "timeout" in lowered:
        return "latency_breach"
    if "connection refused" in lowered or "unavailable" in lowered:
        return "dependency_failure"
    if "oom" in lowered or "killed" in lowered:
        return "resource_pressure"
    if "thrott" in lowered:
        return "resource_pressure"
    if "error" in lowered or "exception" in lowered or "fatal" in lowered:
        return "application_error"
    return "informational"


def classify_anomalies(metrics: Dict[str, Any], latency_threshold_ms: float) -> List[str]:
    anomalies: List[str] = []
    p99 = float(metrics.get("p99_latency_ms", 0.0) or 0.0)
    error_rate = float(metrics.get("error_rate", 0.0) or 0.0)
    throttle = float(metrics.get("cpu_throttling_ratio", 0.0) or 0.0)
    cpu_limit_pct = float(metrics.get("cpu_utilization_pct_of_limit", 0.0) or 0.0)
    mem_limit_pct = float(metrics.get("memory_utilization_pct_of_limit", 0.0) or 0.0)
    if p99 >= latency_threshold_ms:
        anomalies.append("latency_elevated")
    if error_rate > 0.01:
        anomalies.append("error_rate_elevated")
    if throttle >= 0.1:
        anomalies.append("cpu_throttling_elevated")
    if cpu_limit_pct >= 80.0:
        anomalies.append("cpu_pressure")
    if mem_limit_pct >= 80.0:
        anomalies.append("memory_pressure")
    return anomalies


def fingerprint(method: str, inputs: Dict[str, Any]) -> str:
    if method in {"get_k8s_state", "get_metrics", "get_traces", "get_logs"}:
        service = str(inputs.get("service", "")).strip()
        return f"{method}|service={service}"
    if method == "get_dependency_traces":
        service = str(inputs.get("service", "")).strip()
        entry_service = str(inputs.get("entry_service", "frontend")).strip() or "frontend"
        return f"{method}|service={service}|entry_service={entry_service}"
    return method


def canonical_action(tool_name: str, service: str) -> Dict[str, Any]:
    if tool_name == "rollout_undo":
        canonical = f"rollback_deployment:{service}"
    elif tool_name == "restart_pod":
        canonical = f"restart_pod:{service}"
    elif tool_name == "patch_resources":
        canonical = f"patch_resources:{service}"
    elif tool_name == "patch_resources_then_scale":
        canonical = f"patch_resources_then_scale:{service}"
    elif tool_name == "patch_service_selector":
        canonical = f"patch_service_selector:{service}"
    elif tool_name == "patch_service_target_port":
        canonical = f"patch_service_target_port:{service}"
    elif tool_name == "scale_deployment":
        canonical = f"scale_deployment:{service}"
    elif tool_name == "delete_stress_job":
        canonical = f"delete_stress_job:{service}"
    elif tool_name == "wait_and_monitor":
        canonical = "wait_and_monitor"
    else:
        canonical = f"{tool_name}:{service}" if service else tool_name
    if tool_name == "patch_resources":
        tool_equivalents = [f"patch_resources({service}, cpu)"]
    elif tool_name == "patch_resources_then_scale":
        tool_equivalents = [
            f"patch_resources({service}, cpu)",
            f"scale_deployment({service})",
        ]
    elif tool_name == "wait_and_monitor":
        tool_equivalents = ["wait_and_monitor"]
    elif tool_name == "patch_service_selector":
        tool_equivalents = [f"patch_service_selector({service})"]
    elif tool_name == "patch_service_target_port":
        tool_equivalents = [f"patch_service_target_port({service})"]
    elif tool_name == "delete_stress_job":
        tool_equivalents = ["delete_stress_job"]
    else:
        tool_equivalents = [f"{tool_name}({service})"] if service else [tool_name]
    return {"canonical": canonical, "tool_equivalents": tool_equivalents}


def next_episode_path(problem_id: str) -> Path:
    episode_dir = ROOT / "datasets" / "episodes" / problem_id
    for index in range(1, 1000):
        candidate = episode_dir / f"{problem_id}_{index:03d}.json"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"no available episode slot for {problem_id}")


def build_initial_context(problem: Dict[str, Any], summary: Dict[str, Any]) -> str:
    detector = dict((summary.get("steps", {}) or {}).get("detection", {}) or {})
    target = str(problem.get("target_service") or detector.get("config", {}).get("target_deployment", "")).strip()
    category = str(problem.get("category", "")).strip()
    family = str(problem.get("task_family", "")).strip()
    impact = "availability or latency symptoms"
    if category == "resource_latency" or "pressure" in family or "throttle" in family:
        impact = "latency and resource-related symptoms"
    elif "dependency" in family or category == "dependency_trace":
        impact = "request failures or degraded dependency behavior"
    elif category == "availability_control" or "rollout" in family or "service" in family:
        impact = "availability symptoms"

    if target:
        return (
            f"PagerDuty alert: an incident has been detected affecting {target}. "
            f"The monitoring pipeline observed {impact}. "
            "Investigate and recommend the most appropriate remediation action."
        )
    return (
        "PagerDuty alert: an incident has been detected in the Online Boutique cluster. "
        f"The monitoring pipeline observed {impact}. "
        "Investigate and recommend the most appropriate remediation action."
    )


def build_tool_response(record: Dict[str, Any], latency_threshold_ms: float) -> Dict[str, Any]:
    tool = str(record.get("tool", "")).strip()
    output = dict(record.get("output", {}) or {})
    timestamp = str(record.get("timestamp", ""))

    if tool == "get_metrics":
        metrics = dict(output.get("metrics", {}) or {})
        return {
            "service": output.get("service", ""),
            "timestamp": timestamp,
            "metrics": {
                "error_rate_pct": round(float(metrics.get("error_rate", 0.0) or 0.0) * 100.0, 3),
                "latency_p95_ms": float(metrics.get("p95_latency_ms", 0.0) or 0.0),
                "latency_p99_ms": float(metrics.get("p99_latency_ms", 0.0) or 0.0),
                "request_rps": float(metrics.get("request_rps", 0.0) or 0.0),
                "cpu_usage_cores": float(metrics.get("cpu_usage", 0.0) or 0.0),
                "cpu_limit_pct": float(metrics.get("cpu_utilization_pct_of_limit", 0.0) or 0.0),
                "cpu_throttle_pct": round(float(metrics.get("cpu_throttling_ratio", 0.0) or 0.0) * 100.0, 3),
                "memory_limit_pct": float(metrics.get("memory_utilization_pct_of_limit", 0.0) or 0.0),
            },
            "anomalies": classify_anomalies(metrics, latency_threshold_ms),
            "baseline_deltas": {},
            "raw_output": output,
        }

    if tool == "get_logs":
        error_lines = list(output.get("error_lines", []) or [])
        signal_lines = list(output.get("signal_lines", []) or [])
        recent_lines = list(output.get("recent_lines", []) or [])
        lines = signal_lines or error_lines or recent_lines
        return {
            "service": output.get("service", ""),
            "timestamp": timestamp,
            "lines": [
                {
                    "level": "ERROR" if signal_class_for_line(line) != "informational" else "INFO",
                    "msg": line,
                    "signal_class": signal_class_for_line(line),
                }
                for line in lines[:8]
            ],
            "dominant_signal": signal_class_for_line(lines[0]) if lines else "none",
            "raw_output": output,
        }

    if tool == "get_traces":
        call_chain = list(output.get("call_chain", []) or [])
        critical_path = []
        for span in call_chain[:8]:
            critical_path.append(
                {
                    "service": span.get("service", ""),
                    "duration_ms": float(span.get("duration_ms", 0.0) or 0.0),
                    "status": "ERROR" if bool(span.get("error", False)) else "OK",
                    "operation": span.get("operation", ""),
                    "peer_service": span.get("peer_service", ""),
                }
            )
        bottleneck = str(output.get("bottleneck_service", "")).strip()
        return {
            "service": output.get("service", ""),
            "timestamp": timestamp,
            "trace_id": output.get("slowest_trace_id", ""),
            "critical_path": critical_path,
            "bottleneck": bottleneck,
            "error_attribution": (
                f"dominant latency attributed to {bottleneck}" if bottleneck else "no clear bottleneck identified"
            ),
            "trace_quality": output.get("trace_quality", ""),
            "raw_output": output,
        }

    if tool == "get_dependency_traces":
        return {
            "service": output.get("service", ""),
            "timestamp": timestamp,
            "entry_service": output.get("entry_service", ""),
            "downstream_candidates": list(output.get("downstream_candidates", []) or []),
            "bottleneck": output.get("bottleneck_service", ""),
            "summary": output.get("summary", ""),
            "trace_quality": output.get("trace_quality", ""),
            "raw_output": output,
        }

    if tool == "get_k8s_state":
        pod_phases = list(output.get("pod_phases", []) or [])
        recent_events = list(output.get("recent_events", []) or [])
        service_config = dict(output.get("service_config", {}) or {})
        service_config_summary = dict(output.get("service_config_summary", {}) or service_config.get("summary", {}) or {})
        deployment_config = dict(output.get("deployment_config", {}) or {})
        anomalies = []
        if int(output.get("available_replicas", 0) or 0) < int(output.get("desired_replicas", 0) or 0):
            anomalies.append("availability_degraded")
        if any("Unhealthy" == str(event.get("reason", "")) for event in recent_events):
            anomalies.append("probe_failures")
        endpoints = dict(service_config.get("endpoints", {}) or {})
        effective_ready = (
            dict(service_config_summary.get("endpoint_counts", {}) or {}).get("effective_ready")
            if service_config_summary
            else endpoints.get("ready_addresses", 0)
        )
        if service_config and int(effective_ready or 0) == 0:
            anomalies.append("service_has_no_ready_endpoints")
        for anomaly in service_config_summary.get("anomalies", []) or []:
            if anomaly not in anomalies:
                anomalies.append(str(anomaly))
        return {
            "service": output.get("service", ""),
            "timestamp": timestamp,
            "desired_replicas": int(output.get("desired_replicas", 0) or 0),
            "available_replicas": int(output.get("available_replicas", 0) or 0),
            "rollout_progressing": bool(output.get("rollout_progressing", False)),
            "restart_count": int(output.get("restart_count", 0) or 0),
            "pod_phases": pod_phases,
            "service_config_summary": service_config_summary,
            "recent_events": recent_events[:8],
            "deployment_selector": output.get("deployment_selector", {}),
            "deployment_config": deployment_config,
            "service_config": {
                "selector": service_config.get("selector", {}),
                "ports": service_config.get("ports", []),
                "selected_pods": service_config.get("selected_pods", []),
                "deployment_pods": service_config.get("deployment_pods", []),
                "endpoints": {
                    "ready_addresses": endpoints.get("ready_addresses", 0),
                    "not_ready_addresses": endpoints.get("not_ready_addresses", 0),
                    "subsets": endpoints.get("subsets", []),
                    "endpoint_slices": endpoints.get("endpoint_slices", []),
                    "endpoints_error": endpoints.get("endpoints_error"),
                    "endpoint_slices_error": endpoints.get("endpoint_slices_error"),
                },
                "error": service_config.get("error"),
            },
            "anomalies": anomalies,
            "raw_output": output,
        }

    return {"timestamp": timestamp, "raw_output": output}


def normalize_records(run_dir: Path, evidence_report: Dict[str, Any]) -> List[Dict[str, Any]]:
    records = list(evidence_report.get("records", []) or [])
    if records:
        return records

    aci_records = load_jsonl(run_dir / "aci_run_log.jsonl")
    normalized: List[Dict[str, Any]] = []
    for record in aci_records:
        method = str(record.get("method", "")).strip()
        inputs = dict(record.get("inputs", {}) or {})
        outputs = dict(record.get("outputs", {}) or {})
        target = str(inputs.get("service", outputs.get("service", ""))).strip()
        normalized.append(
            {
                "tool": method,
                "target": target,
                "timestamp": record.get("timestamp", ""),
                "richness": "unknown",
                "output": outputs,
                "inputs": inputs,
            }
        )
    return normalized


def main() -> int:
    p = argparse.ArgumentParser(description="Convert a live run artifact directory into a benchmark episode dataset.")
    p.add_argument("run_dir")
    p.add_argument("--benchmark-suite", default=str(ROOT / "benchmark_suite.yaml"))
    p.add_argument("--problem-id", default="")
    p.add_argument("--split", default="dev")
    p.add_argument("--difficulty", default="medium")
    p.add_argument("--out-file", default="")
    args = p.parse_args()

    run_dir = Path(args.run_dir).resolve()
    evidence_report = load_json(run_dir / "evidence_report.json")
    summary = load_json(run_dir / "summary.json")
    suite = load_benchmark_suite(Path(args.benchmark_suite))

    problem = None
    if args.problem_id:
        problem = suite.find_problem_by_id(args.problem_id)
    elif summary.get("problem", {}).get("id"):
        problem = suite.find_problem_by_id(str(summary.get("problem", {}).get("id", "")))
    elif summary.get("experiment_file"):
        problem = suite.find_problem_by_experiment(Path(str(summary.get("experiment_file"))))
    if problem is None:
        raise RuntimeError("unable to resolve benchmark problem for this run")

    detector = dict((summary.get("steps", {}) or {}).get("detection", {}) or {})
    latency_threshold = float((detector.get("config", {}) or {}).get("service_latency_threshold_ms", 250.0) or 250.0)
    records = normalize_records(run_dir, evidence_report)

    tool_responses: Dict[str, Any] = {}
    for record in records:
        tool = str(record.get("tool", "")).strip()
        target = str(record.get("target", "")).strip()
        if not tool or tool == "submit_solution":
            continue
        inputs: Dict[str, Any] = dict(record.get("inputs", {}) or {})
        if target and "service" not in inputs:
            inputs["service"] = target
        if tool == "get_dependency_traces":
            entry_service = str(
                (
                    inputs.get("entry_service")
                    or ((record.get("output", {}) or {}).get("entry_service", problem.entry_service))
                    or problem.entry_service
                )
            )
            inputs["entry_service"] = entry_service
        tool_responses[fingerprint(tool, inputs)] = build_tool_response(record, latency_threshold)

    target_metrics_records = [
        item for item in records if item.get("tool") == "get_metrics" and item.get("target") == problem.target_service
    ]
    target_logs_records = [
        item for item in records if item.get("tool") == "get_logs" and item.get("target") == problem.target_service
    ]
    target_trace_records = [
        item
        for item in records
        if item.get("tool") in {"get_traces", "get_dependency_traces"} and item.get("target") == problem.target_service
    ]
    observability = {
        "metrics_quality": (
            "rich"
            if target_metrics_records and all(item.get("richness", "unknown") in {"rich", "unknown"} for item in target_metrics_records)
            else "weak"
        ),
        "logs_quality": "rich" if target_logs_records else "weak",
        "traces_quality": "rich" if target_trace_records else "weak",
        "summary_counts": dict(evidence_report.get("summary", {}).get("counts", {}) or {}),
    }

    phase = EpisodePhase(
        phase_id=0,
        label="initial_degradation",
        tool_responses=tool_responses,
        observability=observability,
        transitions=[
            EpisodeTransition(
                trigger_type="tool",
                trigger_value="wait_and_monitor",
                target_phase=0,
                label="static_replay",
            )
        ],
    )

    acceptable_actions: List[Dict[str, Any]] = []
    for action in problem.ground_truth.acceptable_actions:
        lowered = action.lower()
        if "targetport" in lowered and "service" in lowered:
            acceptable_actions.append(canonical_action("patch_service_target_port", problem.target_service))
        elif "selector" in lowered and "service" in lowered:
            acceptable_actions.append(canonical_action("patch_service_selector", problem.target_service))
        elif "patch_resources_then_scale" in lowered:
            acceptable_actions.append(canonical_action("patch_resources_then_scale", problem.target_service))
        elif "rollout undo" in lowered:
            acceptable_actions.append(canonical_action("rollout_undo", problem.target_service))
        elif "patch_resources" in lowered:
            acceptable_actions.append(canonical_action("patch_resources", problem.target_service))
        elif "scale_deployment" in lowered or "scale(" in lowered:
            acceptable_actions.append(canonical_action("scale_deployment", problem.target_service))
        elif "stress job" in lowered and "delete" in lowered:
            acceptable_actions.append(canonical_action("delete_stress_job", problem.target_service))
        elif "wait_and_monitor" in lowered:
            acceptable_actions.append(canonical_action("wait_and_monitor", problem.target_service))
    if not acceptable_actions:
        acceptable_actions.append(canonical_action("wait_and_monitor", problem.target_service))
    deduped_actions: List[Dict[str, Any]] = []
    seen = set()
    for action in acceptable_actions:
        canonical = str(action.get("canonical", ""))
        if canonical in seen:
            continue
        seen.add(canonical)
        deduped_actions.append(action)
    acceptable_actions = deduped_actions

    ground_truth = EpisodeGroundTruth(
        root_cause=problem.ground_truth.acceptable_root_causes[0] if problem.ground_truth.acceptable_root_causes else problem.problem_id,
        root_cause_service=problem.target_service,
        fault_class=problem.task_family or problem.category,
        correct_actions=acceptable_actions[:1],
        acceptable_actions=acceptable_actions,
        incorrect_actions=[
            canonical_action("restart_pod", problem.target_service),
            canonical_action("rollout_restart", problem.target_service),
        ],
    )

    telemetry_contract = EpisodeTelemetryContract(
        required_present=[f"{item}" for item in problem.ground_truth.required_evidence],
        required_nonzero=[],
    )

    fault_spec = {
        "type": problem.task_family or problem.category,
        "target_service": problem.target_service,
        "injected_at": "phase_0",
        "parameters": {
            "experiment_file": repo_relative(problem.experiment_file) if problem.experiment_file else "",
            "detector_primary_signal": str((problem.detector_gate or {}).get("primary_signal", "")),
        },
    }

    out_path = Path(args.out_file).resolve() if args.out_file else next_episode_path(problem.problem_id)
    task_id = out_path.stem

    episode = BenchmarkEpisode(
        task_id=task_id,
        family=problem.task_family or problem.category,
        scenario=problem.scenario or problem.problem_id,
        split=args.split,
        difficulty=args.difficulty,
        fault_spec=fault_spec,
        initial_context=build_initial_context(problem.to_dict(), summary),
        phases=[phase],
        ground_truth=ground_truth,
        telemetry_contract=telemetry_contract,
        scoring=EpisodeScoring(),
        provenance=EpisodeProvenance(
            source_run_dir=repo_relative(run_dir),
            captured_from_live_run=True,
            capture_timestamp_utc=str(summary.get("finished_at_utc", summary.get("started_at_utc", ""))),
        ),
    )

    episode.write(out_path)
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
