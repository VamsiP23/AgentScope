#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from agent_graph.aci import AgentCloudInterface  # noqa: E402
from benchmarking.problem import resolve_problem_for_experiment  # noqa: E402
from runner_common import (  # noqa: E402
    DEFAULT_BENCHMARK_SUITE,
    bool_value,
    int_value,
    list_value,
    print_status,
    read_detection_report,
    rel_path,
    require_binary,
    run_cmd,
    run_cmd_streaming,
    sanitize_name,
    sleep_with_progress,
    start_process,
    str_value,
    terminate_process,
    ts_compact,
    ensure_reusable_local_endpoint,
)
from runner_env import build_fault_apply_cmd, build_fault_revert_cmd, build_reset_cmd  # noqa: E402
from runner_agent import build_monitor_cmd  # noqa: E402
from runner_k8s import assess_reset_need, verify_environment  # noqa: E402


TOPOLOGY: Dict[str, List[str]] = {
    "frontend": ["cartservice", "productcatalogservice", "checkoutservice", "recommendationservice", "currencyservice"],
    "checkoutservice": ["cartservice", "productcatalogservice", "paymentservice", "currencyservice", "emailservice", "shippingservice"],
    "recommendationservice": ["productcatalogservice"],
    "cartservice": ["redis-cart"],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_yaml(path: Path) -> Dict[str, Any]:
    payload = yaml.safe_load(path.read_text())
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected YAML mapping in {path}")
    return payload


def _metrics_richness(output: Dict[str, Any]) -> str:
    if output.get("error"):
        return "missing"
    metrics = output.get("metrics", {}) or {}
    if not metrics:
        return "missing"
    resource_available = bool(metrics.get("resource_metrics_available", False))
    application_available = bool(metrics.get("application_metrics_available", False))
    resource_signal_fields = [
        float(metrics.get("cpu_usage", 0.0) or 0.0),
        float(metrics.get("cpu_utilization_pct_of_limit", 0.0) or 0.0),
        float(metrics.get("cpu_throttling_ratio", 0.0) or 0.0),
        float(metrics.get("memory_usage", 0.0) or 0.0),
        float(metrics.get("memory_utilization_pct_of_limit", 0.0) or 0.0),
    ]
    application_signal_fields = [
        float(metrics.get("request_rps", 0.0) or 0.0),
        float(metrics.get("p99_latency_ms", 0.0) or 0.0),
    ]

    has_resource_signal = any(value > 0 for value in resource_signal_fields)
    has_application_signal = any(value > 0 for value in application_signal_fields)

    if resource_available and application_available:
        return "rich" if (has_resource_signal or has_application_signal) else "weak"
    if resource_available:
        return "weak" if has_resource_signal else "missing"
    if application_available:
        return "weak" if has_application_signal else "missing"
    return "missing"


def _logs_richness(output: Dict[str, Any]) -> str:
    error = str(output.get("error", "") or "").lower()
    if "no pods found" in error:
        return "missing"
    if error:
        return "weak"
    if output.get("pods"):
        return "rich"
    return "weak"


def _k8s_richness(output: Dict[str, Any]) -> str:
    if output.get("error"):
        return "missing"
    if output.get("pod_phases") or output.get("recent_events"):
        return "rich"
    return "weak"


def _trace_richness(output: Dict[str, Any]) -> str:
    if bool(output.get("observability_error", False)) or output.get("error"):
        return "missing"
    trace_count = int(output.get("trace_count", 0) or 0)
    quality = str(output.get("trace_quality", "")).strip().lower()
    if trace_count > 0 and quality not in {"missing", "weak"}:
        return "rich"
    if trace_count > 0 or quality == "weak":
        return "weak"
    return "missing"


def _record(tool: str, target: str, output: Dict[str, Any]) -> Dict[str, Any]:
    richness = "weak"
    if tool == "get_metrics":
        richness = _metrics_richness(output)
    elif tool == "get_logs":
        richness = _logs_richness(output)
    elif tool == "get_k8s_state":
        richness = _k8s_richness(output)
    elif tool in {"get_traces", "get_dependency_traces"}:
        richness = _trace_richness(output)

    return {
        "tool": tool,
        "target": target,
        "call_id": output.get("call_id", ""),
        "timestamp": output.get("timestamp", ""),
        "richness": richness,
        "error": output.get("error"),
        "output": output,
    }


def _summarize_records(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts = {"rich": 0, "weak": 0, "missing": 0}
    for record in records:
        counts[record["richness"]] = counts.get(record["richness"], 0) + 1
    return {
        "counts": counts,
        "weak_or_missing": [
            {
                "tool": record["tool"],
                "target": record["target"],
                "richness": record["richness"],
                "error": record["error"],
            }
            for record in records
            if record["richness"] != "rich"
        ],
    }


def _trace_probe_mode(target_service: str, category: str, configured_mode: str) -> str:
    mode = (configured_mode or "").strip()
    if mode:
        return mode
    if category == "dependency_trace":
        if target_service == "frontend":
            return "browse-heavy"
        return "checkout-heavy"
    if target_service == "checkoutservice" or category == "resource_latency":
        return "checkout-heavy"
    return "realistic"


def _trace_records_complete(records: List[Dict[str, Any]]) -> bool:
    trace_records = [record for record in records if record["tool"] in {"get_traces", "get_dependency_traces"}]
    return bool(trace_records) and all(record["richness"] == "rich" for record in trace_records)


def _trace_followup_services(records: List[Dict[str, Any]], target_service: str) -> List[str]:
    followups: List[str] = []
    seen = {target_service}
    for record in records:
        output = dict(record.get("output", {}) or {})
        bottleneck = str(output.get("bottleneck_service", "")).strip()
        if bottleneck and bottleneck not in seen:
            followups.append(bottleneck)
            seen.add(bottleneck)
        for candidate in list(output.get("downstream_candidates", []) or []):
            service = str((candidate or {}).get("service", "")).strip()
            if service and service not in seen:
                followups.append(service)
                seen.add(service)
    return followups[:3]


def _dependency_trace_entry_service(target_service: str, record: Dict[str, Any]) -> str:
    output = dict(record.get("output", {}) or {})
    entry_service = str(output.get("entry_service", "")).strip()
    if entry_service:
        return entry_service
    return target_service


def collect_evidence(
    aci: AgentCloudInterface,
    *,
    target_service: str,
    jaeger_enabled: bool,
    category: str,
    lookback_minutes: int,
    include_dependencies: bool,
    trace_probe_base_url: str,
    trace_probe_mode: str,
    trace_probe_rps: int,
    trace_probe_duration_seconds: int,
    trace_probe_output_root: Path,
    trace_probe_log: Path,
) -> Dict[str, Any]:
    records: List[Dict[str, Any]] = []
    trace_lookback_minutes = max(5, lookback_minutes)
    trace_probe: Dict[str, Any] = {}
    trace_attempts: List[Dict[str, Any]] = []
    effective_include_dependencies = include_dependencies or category == "dependency_trace"

    def add(tool: str, target: str, payload: Dict[str, Any]) -> None:
        records.append(_record(tool, target, payload))

    add("get_k8s_state", target_service, aci.get_k8s_state(target_service))
    add("get_metrics", target_service, aci.get_metrics(target_service, lookback_minutes=lookback_minutes))
    add("get_logs", target_service, aci.get_logs(target_service, tail_lines=120))

    if jaeger_enabled:
        best_trace_records: List[Dict[str, Any]] = []
        best_score = (-1, 999)
        for attempt in range(1, 4):
            current_trace_records: List[Dict[str, Any]] = []
            aci.reset_trace_cache()
            if trace_probe_base_url:
                attempt_root = (
                    trace_probe_output_root
                    if attempt == 1
                    else trace_probe_output_root.parent / f"{trace_probe_output_root.name}_{attempt}"
                )
                attempt_log = (
                    trace_probe_log
                    if attempt == 1
                    else trace_probe_log.with_name(f"{trace_probe_log.stem}_{attempt}.log")
                )
                trace_probe_cmd = [
                    "./scripts/generate_traffic.sh",
                    "-u",
                    trace_probe_base_url,
                    "-d",
                    str(max(1, int(trace_probe_duration_seconds))),
                    "-r",
                    str(max(1, int(trace_probe_rps))),
                    "-m",
                    trace_probe_mode or "realistic",
                    "-o",
                    str(attempt_root),
                ]
                current_probe = run_cmd(trace_probe_cmd, ROOT, attempt_log)
                current_probe["attempt"] = attempt
                current_probe["base_url"] = trace_probe_base_url
                current_probe["mode"] = trace_probe_mode or "realistic"
                current_probe["output_root"] = rel_path(attempt_root)
                trace_attempts.append(current_probe)
                if current_probe["returncode"] == 0:
                    trace_probe = current_probe
                    time.sleep(5)

            current_trace_records.append(
                _record("get_traces", target_service, aci.get_traces(target_service, lookback_minutes=trace_lookback_minutes))
            )
            if category == "resource_latency" and target_service != "frontend":
                current_trace_records.append(
                    _record("get_traces", "frontend", aci.get_traces("frontend", lookback_minutes=trace_lookback_minutes))
                )
                current_trace_records.append(
                    _record(
                        "get_dependency_traces",
                        target_service,
                        aci.get_dependency_traces(
                            target_service,
                            entry_service="frontend",
                            lookback_minutes=trace_lookback_minutes,
                        ),
                    )
                )
            elif category == "dependency_trace":
                current_trace_records.append(
                    _record(
                        "get_dependency_traces",
                        target_service,
                        aci.get_dependency_traces(
                            target_service,
                            entry_service="frontend",
                            lookback_minutes=trace_lookback_minutes,
                        ),
                    )
                )

            counts = _summarize_records(current_trace_records)["counts"]
            score = (counts["rich"], counts["missing"])
            if score[0] > best_score[0] or (score[0] == best_score[0] and score[1] < best_score[1]):
                best_trace_records = current_trace_records
                best_score = score
            if _trace_records_complete(current_trace_records):
                best_trace_records = current_trace_records
                break

        records.extend(best_trace_records)
        for followup_service in _trace_followup_services(best_trace_records, target_service):
            add("get_k8s_state", followup_service, aci.get_k8s_state(followup_service))
            add("get_metrics", followup_service, aci.get_metrics(followup_service, lookback_minutes=lookback_minutes))
            add("get_logs", followup_service, aci.get_logs(followup_service, tail_lines=80))
        if category == "dependency_trace":
            for record in best_trace_records:
                if record.get("tool") != "get_dependency_traces":
                    continue
                entry_service = _dependency_trace_entry_service(target_service, record)
                for followup_service in _trace_followup_services([record], target_service)[:2]:
                    add(
                        "get_dependency_traces",
                        followup_service,
                        aci.get_dependency_traces(
                            followup_service,
                            entry_service=entry_service,
                            lookback_minutes=trace_lookback_minutes,
                        ),
                    )

    if effective_include_dependencies:
        for dependency in TOPOLOGY.get(target_service, []):
            add("get_k8s_state", dependency, aci.get_k8s_state(dependency))
            add("get_metrics", dependency, aci.get_metrics(dependency, lookback_minutes=lookback_minutes))
            add("get_logs", dependency, aci.get_logs(dependency, tail_lines=80))

    return {
        "collected_at_utc": utc_now(),
        "trace_probe": trace_probe,
        "trace_attempts": trace_attempts,
        "records": records,
        "summary": _summarize_records(records),
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run an experiment without the agent and collect the exact ACI evidence available during the fault.")
    p.add_argument("experiment_file", help="Path to experiment YAML file")
    p.add_argument("--out-dir", default=str(ROOT / "experiment_runs"), help="Run artifact root")
    p.add_argument("--skip-startup", action="store_true", help="Skip startup even if the experiment enables it")
    p.add_argument(
        "--skip-reset",
        action="store_true",
        help="Skip reset.before_run even if the experiment enables it",
    )
    p.add_argument(
        "--warm-cluster",
        action="store_true",
        help=(
            "Fast collection mode for an already-healthy cluster: skip startup and "
            "reset, but still verify the environment and clean up the active fault."
        ),
    )
    p.add_argument("--include-dependencies", action="store_true", help="Also collect evidence for the target service's direct dependencies")
    p.add_argument("--lookback-minutes", type=int, default=1, help="Prometheus/Jaeger lookback for evidence collection")
    p.add_argument(
        "--wait-for-detector",
        action="store_true",
        help="Wait for detector confirmation before collecting evidence. Off by default for offline collection.",
    )
    return p


def main() -> int:
    args = build_parser().parse_args()
    skip_startup = bool(args.skip_startup or args.warm_cluster)
    skip_reset = bool(args.skip_reset or args.warm_cluster)

    require_binary("kubectl")
    require_binary("python3")

    experiment_path = Path(args.experiment_file)
    if not experiment_path.is_absolute():
        experiment_path = (ROOT / experiment_path).resolve()
    if not experiment_path.exists():
        raise RuntimeError(f"Experiment file not found: {experiment_path}")

    config = _read_yaml(experiment_path)
    name = sanitize_name(f"{str_value(config.get('name'), experiment_path.stem)}_evidence")
    namespace = str_value(config.get("namespace"), "default")
    timings = config.get("timings", {}) or {}
    pre_fault_delay = int_value(timings.get("pre_fault_delay_seconds"), 60)
    post_fault_delay = int_value(timings.get("post_fault_delay_seconds"), 30)
    evidence_collection_delay = int_value(
        timings.get("evidence_collection_delay_seconds"),
        min(max(post_fault_delay, 0), 20),
    )
    detector = config.get("detector", {}) or {}
    traffic = config.get("traffic", {}) or {}
    fault_cfg = config.get("fault", {}) or {}
    reset_cfg = config.get("reset", {}) or {}
    agent_cfg = config.get("agent", {}) or {}

    run_dir = Path(args.out_dir).resolve() / f"{ts_compact()}_{name}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "experiment.yaml").write_text(experiment_path.read_text())

    print_status(f"starting evidence probe '{name}'")
    print_status(f"artifacts directory: {run_dir}")

    summary: Dict[str, Any] = {
        "name": str_value(config.get("name"), experiment_path.stem),
        "run_id": run_dir.name,
        "started_at_utc": utc_now(),
        "experiment_file": str(experiment_path),
        "namespace": namespace,
        "mode": "evidence_probe",
        "warm_cluster": bool(args.warm_cluster),
        "skip_startup": skip_startup,
        "skip_reset": skip_reset,
        "steps": {},
    }

    traffic_proc = None
    baseline_proc = None
    monitor_proc = None
    fault_active = False

    try:
        startup = config.get("startup", {}) or {}
        startup_enabled = bool_value(startup.get("enabled"), True) and not skip_startup
        if startup_enabled:
            print_status("phase=startup: running start_all.sh")
            cmd = ["./scripts/start_all.sh", "-n", namespace]
            cmd.extend(list_value(startup.get("args")))
            summary["steps"]["startup"] = run_cmd(cmd, ROOT, run_dir / "startup.log")
            if summary["steps"]["startup"]["returncode"] != 0:
                raise RuntimeError("start_all.sh failed; see startup.log")
        else:
            print_status("phase=startup: skipped")

        if skip_reset:
            summary["steps"]["reset_before"] = {
                "skipped": True,
                "reason": "skip-reset/warm-cluster requested",
                "finished_at_utc": utc_now(),
            }
            print_status("phase=reset: skipped (warm cluster)")
        elif bool_value(reset_cfg.get("enabled"), False) and bool_value(reset_cfg.get("before_run"), True):
            summary["steps"]["reset_before_check"] = assess_reset_need(namespace)
            if summary["steps"]["reset_before_check"]["needs_reset"]:
                print_status("phase=reset: restoring cluster baseline")
                reset_cmd = build_reset_cmd(namespace, reset_cfg)
                summary["steps"]["reset_before"] = run_cmd_streaming(
                    reset_cmd,
                    ROOT,
                    run_dir / "reset_before.log",
                    stdout_prefix="[reset] ",
                )
                if summary["steps"]["reset_before"]["returncode"] != 0:
                    raise RuntimeError("cluster reset failed before run; see reset_before.log")
            else:
                print_status("phase=reset: skipped (cluster baseline already healthy)")

        verify_environment(namespace)
        print_status("phase=environment: verified")

        prom_url = str_value(detector.get("prom_url"), "http://localhost:9090")
        jaeger_url = str_value(agent_cfg.get("jaeger_url"), "http://localhost:16686")
        frontend_base_url = str_value(traffic.get("base_url"), "http://localhost:8080")
        summary["steps"]["port_forward_prometheus"] = ensure_reusable_local_endpoint(namespace, "prometheus", prom_url, "/-/ready")
        summary["steps"]["port_forward_jaeger"] = ensure_reusable_local_endpoint(namespace, "jaeger", jaeger_url, "/api/services")
        if (urlparse(frontend_base_url).hostname or "").lower() in {"localhost", "127.0.0.1"}:
            summary["steps"]["port_forward_frontend"] = ensure_reusable_local_endpoint(
                namespace,
                "frontend-external",
                frontend_base_url,
                "/_healthz",
                remote_port=80,
            )

        if bool_value(traffic.get("enabled"), False):
            traffic_cmd = [
                "./scripts/generate_traffic.sh",
                "-u",
                frontend_base_url,
                "-d",
                str(int_value(traffic.get("duration_seconds"), 300)),
                "-r",
                str(int_value(traffic.get("rps"), 1)),
                "-m",
                str_value(traffic.get("mode"), "realistic"),
            ]
            traffic_proc = start_process(traffic_cmd, ROOT, run_dir / "traffic.log")
            summary["steps"]["traffic"] = {"cmd": traffic_cmd, "pid": traffic_proc.pid}
            print_status(f"phase=traffic: started (pid={traffic_proc.pid})")

        baseline = config.get("baseline", {}) or {}
        if bool_value(baseline.get("enabled"), False):
            baseline_cmd = [
                "./scripts/collect_baseline.sh",
                "-n",
                namespace,
                "-i",
                str(int_value(baseline.get("interval_seconds"), 15)),
                "-d",
                str(int_value(baseline.get("duration_seconds"), 300)),
            ]
            baseline_proc = start_process(baseline_cmd, ROOT, run_dir / "baseline.log")
            summary["steps"]["baseline"] = {"cmd": baseline_cmd, "pid": baseline_proc.pid}
            print_status(f"phase=baseline: started (pid={baseline_proc.pid})")

        if bool_value(detector.get("enabled"), False):
            monitor_cmd = build_monitor_cmd(namespace, detector, run_dir)
            monitor_proc = start_process(
                monitor_cmd,
                ROOT,
                run_dir / "monitor.log",
                mirror_stdout=True,
                stdout_prefix="[monitor] ",
            )
            summary["steps"]["monitor"] = {"cmd": monitor_cmd, "pid": monitor_proc.pid}
            print_status(f"phase=monitor: started (pid={monitor_proc.pid})")

        sleep_with_progress(pre_fault_delay, "phase=pre_fault_delay")

        if fault_cfg:
            print_status("phase=fault_apply: applying fault")
            apply_cmd = build_fault_apply_cmd(namespace, fault_cfg)
            summary["steps"]["fault_apply"] = run_cmd(apply_cmd, ROOT, run_dir / "fault_apply.log")
            if summary["steps"]["fault_apply"]["returncode"] != 0:
                raise RuntimeError("fault apply failed; see fault_apply.log")
            fault_active = True
            print_status("phase=fault_apply: completed")

        detection = {}
        if bool_value(detector.get("enabled"), False):
            latest_detection_path = run_dir / "detector_runs" / "latest_detection.json"
            if args.wait_for_detector:
                max_wait = 120
                poll_interval = 2
                print_status(f"phase=evidence_wait: waiting up to {max_wait}s for detector confirmation")
                deadline = time.time() + max_wait
                last_summary = ""
                while time.time() <= deadline:
                    detection = read_detection_report(latest_detection_path)
                    if detection:
                        summary_text = str(detection.get("summary", ""))
                        if summary_text and summary_text != last_summary:
                            print_status(f"phase=agent_wait: detector summary='{summary_text}'")
                            last_summary = summary_text
                        if detection.get("incident_detected", False):
                            break
                    time.sleep(max(1, poll_interval))
            else:
                if evidence_collection_delay > 0:
                    print_status(
                        "phase=evidence_delay: waiting "
                        f"{evidence_collection_delay}s after fault injection before collecting evidence"
                    )
                    sleep_with_progress(evidence_collection_delay, "phase=evidence_delay")
                detection = read_detection_report(latest_detection_path)

            (run_dir / "seeded_detection.json").write_text(json.dumps(detection, indent=2))
            summary["steps"]["detection"] = detection
        elif evidence_collection_delay > 0:
            print_status(
                "phase=evidence_delay: waiting "
                f"{evidence_collection_delay}s after fault injection before collecting evidence"
            )
            sleep_with_progress(evidence_collection_delay, "phase=evidence_delay")

        print_status("phase=evidence: collecting ACI evidence")
        benchmark_problem = resolve_problem_for_experiment(experiment_path, DEFAULT_BENCHMARK_SUITE)
        target_service = ""
        category = ""
        if benchmark_problem is not None:
            target_service = benchmark_problem.target_service
            category = benchmark_problem.category
        if not target_service:
            target_service = str_value(agent_cfg.get("target_deployment"), str_value(detector.get("target_deployment"), ""))
        if not target_service:
            raise RuntimeError("Could not determine target service for evidence probe")

        aci = AgentCloudInterface(
            namespace=namespace,
            prom_url=prom_url,
            jaeger_url=jaeger_url,
            jaeger_enabled=bool_value(agent_cfg.get("jaeger_enabled"), True),
            dry_run=True,
            run_log_path=str(run_dir / "aci_run_log.jsonl"),
        )
        evidence = collect_evidence(
            aci,
            target_service=target_service,
            jaeger_enabled=bool_value(agent_cfg.get("jaeger_enabled"), True),
            category=category,
            lookback_minutes=max(1, args.lookback_minutes),
            include_dependencies=bool(args.include_dependencies),
            trace_probe_base_url=frontend_base_url if bool_value(agent_cfg.get("jaeger_enabled"), True) else "",
            trace_probe_mode=_trace_probe_mode(target_service, category, str_value(traffic.get("mode"), "")),
            trace_probe_rps=max(6, min(20, int_value(traffic.get("rps"), 8))),
            trace_probe_duration_seconds=12,
            trace_probe_output_root=run_dir / "trace_probe_traffic",
            trace_probe_log=run_dir / "trace_probe.log",
        )
        evidence["target_service"] = target_service
        evidence["category"] = category
        evidence["detector_snapshot"] = detection
        (run_dir / "evidence_report.json").write_text(json.dumps(evidence, indent=2))
        summary["steps"]["evidence"] = {
            "target_service": target_service,
            "category": category,
            "counts": evidence["summary"]["counts"],
            "trace_probe": evidence.get("trace_probe", {}),
            "report_file": rel_path(run_dir / "evidence_report.json"),
            "aci_run_log": rel_path(run_dir / "aci_run_log.jsonl"),
        }
        print_status(f"phase=evidence: collected for target={target_service}")

        sleep_with_progress(post_fault_delay, "phase=post_fault_delay")

        if fault_active:
            print_status("phase=fault_revert: reverting active fault")
            revert_cmd = build_fault_revert_cmd(namespace, fault_cfg)
            summary["steps"]["fault_revert"] = run_cmd(revert_cmd, ROOT, run_dir / "fault_revert.log")
            if summary["steps"]["fault_revert"]["returncode"] != 0:
                raise RuntimeError("fault revert failed; see fault_revert.log")
            fault_active = False

    finally:
        if fault_active:
            try:
                print_status("phase=fault_revert_on_exit: reverting active fault")
                revert_cmd = build_fault_revert_cmd(namespace, fault_cfg)
                summary["steps"]["fault_revert_on_exit"] = run_cmd(
                    revert_cmd,
                    ROOT,
                    run_dir / "fault_revert_on_exit.log",
                )
            except Exception as exc:
                summary["steps"]["fault_revert_on_exit"] = {"error": str(exc)}
        if traffic_proc is not None:
            summary["steps"]["traffic_exit"] = {"returncode": terminate_process(traffic_proc)}
        if baseline_proc is not None:
            summary["steps"]["baseline_exit"] = {"returncode": terminate_process(baseline_proc)}
        if monitor_proc is not None:
            summary["steps"]["monitor_exit"] = {"returncode": terminate_process(monitor_proc)}

        summary["finished_at_utc"] = utc_now()
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
