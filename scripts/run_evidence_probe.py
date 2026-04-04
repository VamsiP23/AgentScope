#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_experiment as runner  # noqa: E402
from agent_graph.aci import AgentCloudInterface  # noqa: E402
from benchmarking.problem import resolve_problem_for_experiment  # noqa: E402


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


def collect_evidence(
    aci: AgentCloudInterface,
    *,
    target_service: str,
    jaeger_enabled: bool,
    category: str,
    lookback_minutes: int,
    include_dependencies: bool,
) -> Dict[str, Any]:
    records: List[Dict[str, Any]] = []

    def add(tool: str, target: str, payload: Dict[str, Any]) -> None:
        records.append(_record(tool, target, payload))

    add("get_k8s_state", target_service, aci.get_k8s_state(target_service))
    add("get_metrics", target_service, aci.get_metrics(target_service, lookback_minutes=lookback_minutes))
    add("get_logs", target_service, aci.get_logs(target_service, tail_lines=120))

    if jaeger_enabled:
        add("get_traces", target_service, aci.get_traces(target_service, lookback_minutes=lookback_minutes))
        if category in {"resource_latency", "dependency_trace"}:
            add("get_traces", "frontend", aci.get_traces("frontend", lookback_minutes=lookback_minutes))
            if target_service != "frontend":
                add(
                    "get_dependency_traces",
                    target_service,
                    aci.get_dependency_traces(
                        target_service,
                        entry_service="frontend",
                        lookback_minutes=lookback_minutes,
                    ),
                )

    if include_dependencies:
        for dependency in TOPOLOGY.get(target_service, []):
            add("get_k8s_state", dependency, aci.get_k8s_state(dependency))
            add("get_metrics", dependency, aci.get_metrics(dependency, lookback_minutes=lookback_minutes))
            add("get_logs", dependency, aci.get_logs(dependency, tail_lines=80))

    return {
        "collected_at_utc": utc_now(),
        "records": records,
        "summary": _summarize_records(records),
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run an experiment without the agent and collect the exact ACI evidence available during the fault.")
    p.add_argument("experiment_file", help="Path to experiment YAML file")
    p.add_argument("--out-dir", default=str(ROOT / "experiment_runs"), help="Run artifact root")
    p.add_argument("--skip-startup", action="store_true", help="Skip startup even if the experiment enables it")
    p.add_argument("--include-dependencies", action="store_true", help="Also collect evidence for the target service's direct dependencies")
    p.add_argument("--lookback-minutes", type=int, default=1, help="Prometheus/Jaeger lookback for evidence collection")
    return p


def main() -> int:
    args = build_parser().parse_args()

    runner.require_binary("kubectl")
    runner.require_binary("python3")

    experiment_path = Path(args.experiment_file)
    if not experiment_path.is_absolute():
        experiment_path = (ROOT / experiment_path).resolve()
    if not experiment_path.exists():
        raise RuntimeError(f"Experiment file not found: {experiment_path}")

    config = _read_yaml(experiment_path)
    name = runner.sanitize_name(f"{runner.str_value(config.get('name'), experiment_path.stem)}_evidence")
    namespace = runner.str_value(config.get("namespace"), "default")
    timings = config.get("timings", {}) or {}
    pre_fault_delay = runner.int_value(timings.get("pre_fault_delay_seconds"), 60)
    post_fault_delay = runner.int_value(timings.get("post_fault_delay_seconds"), 30)
    detector = config.get("detector", {}) or {}
    traffic = config.get("traffic", {}) or {}
    fault_cfg = config.get("fault", {}) or {}
    reset_cfg = config.get("reset", {}) or {}
    agent_cfg = config.get("agent", {}) or {}

    run_dir = Path(args.out_dir).resolve() / f"{runner.ts_compact()}_{name}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "experiment.yaml").write_text(experiment_path.read_text())

    runner.print_status(f"starting evidence probe '{name}'")
    runner.print_status(f"artifacts directory: {run_dir}")

    summary: Dict[str, Any] = {
        "name": runner.str_value(config.get("name"), experiment_path.stem),
        "run_id": run_dir.name,
        "started_at_utc": utc_now(),
        "experiment_file": str(experiment_path),
        "namespace": namespace,
        "mode": "evidence_probe",
        "steps": {},
    }

    traffic_proc = None
    baseline_proc = None
    monitor_proc = None
    fault_active = False

    try:
        startup = config.get("startup", {}) or {}
        startup_enabled = runner.bool_value(startup.get("enabled"), True) and not args.skip_startup
        if startup_enabled:
            runner.print_status("phase=startup: running start_all.sh")
            cmd = ["./scripts/start_all.sh", "-n", namespace]
            cmd.extend(runner.list_value(startup.get("args")))
            summary["steps"]["startup"] = runner.run_cmd(cmd, ROOT, run_dir / "startup.log")
            if summary["steps"]["startup"]["returncode"] != 0:
                raise RuntimeError("start_all.sh failed; see startup.log")
        else:
            runner.print_status("phase=startup: skipped")

        if runner.bool_value(reset_cfg.get("enabled"), False) and runner.bool_value(reset_cfg.get("before_run"), True):
            summary["steps"]["reset_before_check"] = runner.assess_reset_need(namespace)
            if summary["steps"]["reset_before_check"]["needs_reset"]:
                runner.print_status("phase=reset: restoring cluster baseline")
                reset_cmd = runner.build_reset_cmd(namespace, reset_cfg)
                summary["steps"]["reset_before"] = runner.run_cmd_streaming(
                    reset_cmd,
                    ROOT,
                    run_dir / "reset_before.log",
                    stdout_prefix="[reset] ",
                )
                if summary["steps"]["reset_before"]["returncode"] != 0:
                    raise RuntimeError("cluster reset failed before run; see reset_before.log")
            else:
                runner.print_status("phase=reset: skipped (cluster baseline already healthy)")

        runner.verify_environment(namespace)
        runner.verify_chaos_mesh_health()
        runner.print_status("phase=environment: verified")

        prom_url = runner.str_value(detector.get("prom_url"), "http://localhost:9090")
        jaeger_url = runner.str_value(agent_cfg.get("jaeger_url"), "http://localhost:16686")
        summary["steps"]["port_forward_prometheus"] = runner.ensure_reusable_local_endpoint(namespace, "prometheus", prom_url, "/-/ready")
        summary["steps"]["port_forward_jaeger"] = runner.ensure_reusable_local_endpoint(namespace, "jaeger", jaeger_url, "/api/services")

        if runner.bool_value(traffic.get("enabled"), False):
            traffic_cmd = [
                "./scripts/generate_traffic.sh",
                "-u",
                runner.str_value(traffic.get("base_url"), "http://localhost:8080"),
                "-d",
                str(runner.int_value(traffic.get("duration_seconds"), 300)),
                "-r",
                str(runner.int_value(traffic.get("rps"), 1)),
                "-m",
                runner.str_value(traffic.get("mode"), "realistic"),
            ]
            traffic_proc = runner.start_process(traffic_cmd, ROOT, run_dir / "traffic.log")
            summary["steps"]["traffic"] = {"cmd": traffic_cmd, "pid": traffic_proc.pid}
            runner.print_status(f"phase=traffic: started (pid={traffic_proc.pid})")

        baseline = config.get("baseline", {}) or {}
        if runner.bool_value(baseline.get("enabled"), False):
            baseline_cmd = [
                "./scripts/collect_baseline.sh",
                "-n",
                namespace,
                "-i",
                str(runner.int_value(baseline.get("interval_seconds"), 15)),
                "-d",
                str(runner.int_value(baseline.get("duration_seconds"), 300)),
            ]
            baseline_proc = runner.start_process(baseline_cmd, ROOT, run_dir / "baseline.log")
            summary["steps"]["baseline"] = {"cmd": baseline_cmd, "pid": baseline_proc.pid}
            runner.print_status(f"phase=baseline: started (pid={baseline_proc.pid})")

        if runner.bool_value(detector.get("enabled"), False):
            monitor_cmd = runner.build_monitor_cmd(namespace, detector, run_dir)
            monitor_proc = runner.start_process(
                monitor_cmd,
                ROOT,
                run_dir / "monitor.log",
                mirror_stdout=True,
                stdout_prefix="[monitor] ",
            )
            summary["steps"]["monitor"] = {"cmd": monitor_cmd, "pid": monitor_proc.pid}
            runner.print_status(f"phase=monitor: started (pid={monitor_proc.pid})")

        runner.sleep_with_progress(pre_fault_delay, "phase=pre_fault_delay")

        if fault_cfg:
            runner.print_status("phase=fault_apply: applying fault")
            apply_cmd = runner.build_fault_apply_cmd(namespace, fault_cfg)
            summary["steps"]["fault_apply"] = runner.run_cmd(apply_cmd, ROOT, run_dir / "fault_apply.log")
            if summary["steps"]["fault_apply"]["returncode"] != 0:
                raise RuntimeError("fault apply failed; see fault_apply.log")
            fault_active = True
            runner.print_status("phase=fault_apply: completed")

        detection = {}
        if runner.bool_value(detector.get("enabled"), False):
            max_wait = 120
            poll_interval = 2
            runner.print_status(f"phase=evidence_wait: waiting up to {max_wait}s for detector confirmation")
            detection = runner.wait_for_incident(run_dir / "detector_runs", max_wait, poll_interval)
            (run_dir / "seeded_detection.json").write_text(json.dumps(detection, indent=2))
            summary["steps"]["detection"] = detection

        runner.print_status("phase=evidence: collecting ACI evidence")
        benchmark_problem = resolve_problem_for_experiment(experiment_path, runner.DEFAULT_BENCHMARK_SUITE)
        target_service = ""
        category = ""
        if benchmark_problem is not None:
            target_service = benchmark_problem.target_service
            category = benchmark_problem.category
        if not target_service:
            target_service = runner.str_value(agent_cfg.get("target_deployment"), runner.str_value(detector.get("target_deployment"), ""))
        if not target_service:
            raise RuntimeError("Could not determine target service for evidence probe")

        aci = AgentCloudInterface(
            namespace=namespace,
            prom_url=prom_url,
            jaeger_url=jaeger_url,
            jaeger_enabled=runner.bool_value(agent_cfg.get("jaeger_enabled"), True),
            dry_run=True,
            run_log_path=str(run_dir / "aci_run_log.jsonl"),
        )
        evidence = collect_evidence(
            aci,
            target_service=target_service,
            jaeger_enabled=runner.bool_value(agent_cfg.get("jaeger_enabled"), True),
            category=category,
            lookback_minutes=max(1, args.lookback_minutes),
            include_dependencies=bool(args.include_dependencies),
        )
        evidence["target_service"] = target_service
        evidence["category"] = category
        evidence["detector_snapshot"] = detection
        (run_dir / "evidence_report.json").write_text(json.dumps(evidence, indent=2))
        summary["steps"]["evidence"] = {
            "target_service": target_service,
            "category": category,
            "counts": evidence["summary"]["counts"],
            "report_file": runner.rel_path(run_dir / "evidence_report.json"),
            "aci_run_log": runner.rel_path(run_dir / "aci_run_log.jsonl"),
        }
        runner.print_status(f"phase=evidence: collected for target={target_service}")

        runner.sleep_with_progress(post_fault_delay, "phase=post_fault_delay")

        if fault_active and not runner.bool_value(fault_cfg.get("auto_revert"), False):
            runner.print_status("phase=fault_revert: reverting active fault")
            revert_cmd = runner.build_fault_revert_cmd(namespace, fault_cfg)
            summary["steps"]["fault_revert"] = runner.run_cmd(revert_cmd, ROOT, run_dir / "fault_revert.log")
            if summary["steps"]["fault_revert"]["returncode"] != 0:
                raise RuntimeError("fault revert failed; see fault_revert.log")
            fault_active = False

    finally:
        if fault_active:
            try:
                runner.print_status("phase=fault_revert_on_exit: reverting active fault")
                revert_cmd = runner.build_fault_revert_cmd(namespace, fault_cfg)
                summary["steps"]["fault_revert_on_exit"] = runner.run_cmd(
                    revert_cmd,
                    ROOT,
                    run_dir / "fault_revert_on_exit.log",
                )
            except Exception as exc:
                summary["steps"]["fault_revert_on_exit"] = {"error": str(exc)}
        if traffic_proc is not None:
            summary["steps"]["traffic_exit"] = {"returncode": runner.terminate_process(traffic_proc)}
        if baseline_proc is not None:
            summary["steps"]["baseline_exit"] = {"returncode": runner.terminate_process(baseline_proc)}
        if monitor_proc is not None:
            summary["steps"]["monitor_exit"] = {"returncode": runner.terminate_process(monitor_proc)}

        summary["finished_at_utc"] = utc_now()
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
