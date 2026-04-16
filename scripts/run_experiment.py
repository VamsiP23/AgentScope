#!/usr/bin/env python3
"""Run an AgentScope experiment from a YAML definition.

The runner orchestrates:
1. Optional environment startup.
2. Optional synthetic traffic and baseline collection.
3. Fault injection from an experiment YAML.
4. Run artifact collection under experiment_runs/<timestamp>_<name>/.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarking.evaluator import evaluate_agent_run
from benchmarking.problem import ProblemSpec, resolve_problem_for_experiment
from benchmarking.reproducibility import evaluate_telemetry_contract
from runner_common import (
    DEFAULT_BENCHMARK_SUITE,
    DEFAULT_OUT_DIR,
    ROOT,
    bool_value,
    epoch_to_utc,
    finish_process,
    int_value,
    list_value,
    print_status,
    read_json_report,
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
    utc_now,
    ensure_reusable_local_endpoint,
)
from runner_env import (
    build_fault_apply_cmd,
    build_fault_revert_cmd,
    build_reset_cmd,
    load_yaml,
)
from runner_agent import (
    build_agent_cmd,
    build_monitor_cmd,
    ensure_ollama_model_available,
    prewarm_agent_runtime,
    validate_telemetry_sources,
    wait_for_incident,
)
from runner_k8s import (
    assess_reset_need,
    capture_snapshot,
    cleanup_existing_native_faults,
    collect_window_metrics,
    verify_environment,
)


def write_evaluation_artifact(
    problem: ProblemSpec | None,
    agent_report: Dict[str, Any],
    out_path: Path,
) -> Dict[str, Any]:
    if problem is None:
        payload = {
            "problem_id": "",
            "status": "unmapped",
            "error": "no benchmark problem mapped for this experiment",
        }
        out_path.write_text(json.dumps(payload, indent=2))
        return payload

    evaluation = evaluate_agent_run(problem, agent_report).to_dict()
    out_path.write_text(json.dumps(evaluation, indent=2))
    return evaluation


def write_episode_artifact(
    *,
    run_dir: Path,
    summary: Dict[str, Any],
    experiment_path: Path,
    benchmark_suite_path: Path,
    problem: ProblemSpec | None,
    config: Dict[str, Any],
    agent_report: Dict[str, Any],
    evaluation: Dict[str, Any],
) -> Dict[str, Any]:
    agent_cfg = config.get("agent", {}) or {}
    detector_cfg = config.get("detector", {}) or {}
    fault_cfg = config.get("fault", {}) or {}
    timings_cfg = config.get("timings", {}) or {}
    baseline_cfg = config.get("baseline", {}) or {}
    traffic_cfg = config.get("traffic", {}) or {}
    telemetry_validation = dict((summary.get("steps", {}) or {}).get("telemetry_validation", {}) or {})
    telemetry_contract = dict((summary.get("steps", {}) or {}).get("telemetry_contract", {}) or {})
    solution = dict(agent_report.get("solution", {}) or {})

    payload = {
        "episode_id": str(summary.get("run_id", run_dir.name)),
        "mode": "live",
        "status": str(summary.get("result", "")),
        "started_at_utc": str(summary.get("started_at_utc", "")),
        "finished_at_utc": str(summary.get("finished_at_utc", "")),
        "experiment": {
            "name": str(summary.get("name", experiment_path.stem)),
            "file": str(experiment_path),
            "namespace": str(summary.get("namespace", "")),
            "benchmark_suite": str(benchmark_suite_path),
        },
        "task": problem.to_dict() if problem is not None else {},
        "fault": {
            "filepath": str(fault_cfg.get("filepath", "")),
            "apply_cmd": list(fault_cfg.get("apply_cmd", []) or []),
            "revert_cmd": list(fault_cfg.get("revert_cmd", []) or []),
            "duration_seconds": int(fault_cfg.get("duration_seconds", 0) or 0),
            "auto_revert": bool(fault_cfg.get("auto_revert", False)),
        },
        "budgets": {
            "pre_fault_delay_seconds": int(timings_cfg.get("pre_fault_delay_seconds", 0) or 0),
            "post_fault_delay_seconds": int(timings_cfg.get("post_fault_delay_seconds", 0) or 0),
            "agent_max_steps": int(agent_cfg.get("max_steps", 0) or 0),
            "agent_wait_timeout_seconds": int(agent_cfg.get("wait_for_incident_timeout_seconds", 0) or 0),
            "baseline_duration_seconds": int(baseline_cfg.get("duration_seconds", 0) or 0),
            "traffic_duration_seconds": int(traffic_cfg.get("duration_seconds", 0) or 0),
        },
        "detection": dict((summary.get("steps", {}) or {}).get("detection", {}) or {}),
        "seeded_detection": dict(agent_report.get("seeded_detection", {}) or {}),
        "telemetry": {
            "validation": telemetry_validation,
            "contract": telemetry_contract,
        },
        "agent": {
            "enabled": bool(agent_cfg.get("enabled", False)),
            "type": str(agent_cfg.get("type", "")),
            "provider": str(agent_report.get("provider", "")),
            "model": str(agent_report.get("model", "")),
            "variant": str(agent_report.get("agent_variant", "")),
            "dry_run": bool(agent_cfg.get("dry_run", False)),
            "steps": list(agent_report.get("steps", []) or []),
            "guardrail_events": list(agent_report.get("guardrail_events", []) or []),
            "solution": solution,
        },
        "evaluation": dict(evaluation or {}),
        "artifacts": {
            "run_dir": str(run_dir),
            "summary": str(run_dir / "summary.json"),
            "evaluation": str(run_dir / "evaluation.json"),
            "agent_report": str(run_dir / "agent_report.json"),
            "seeded_detection": str(run_dir / "seeded_detection.json"),
            "aci_run_log": str(run_dir / "aci_run_log.jsonl"),
            "baseline_metrics": str(run_dir / "baseline_metrics.json"),
            "fault_metrics": str(run_dir / "fault_metrics.json"),
            "episode": str(run_dir / "episode.json"),
        },
        "error": str(summary.get("error", "")),
    }
    out_path = run_dir / "episode.json"
    out_path.write_text(json.dumps(payload, indent=2))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an experiment from a YAML file.")
    parser.add_argument("experiment_file", help="Path to experiment YAML file")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Run artifact root")
    parser.add_argument(
        "--skip-startup",
        action="store_true",
        help="Skip calling start_all.sh even if startup.enabled is true in the YAML",
    )
    args = parser.parse_args()

    require_binary("kubectl")
    require_binary("python3")

    experiment_path = Path(args.experiment_file)
    if not experiment_path.is_absolute():
        experiment_path = (ROOT / experiment_path).resolve()
    if not experiment_path.exists():
        raise RuntimeError(f"Experiment file not found: {experiment_path}")

    config = load_yaml(experiment_path)
    name = sanitize_name(str_value(config.get("name"), experiment_path.stem))
    namespace = str_value(config.get("namespace"), "default")
    timings = config.get("timings", {}) or {}
    pre_fault_delay = int_value(timings.get("pre_fault_delay_seconds"), 60)
    post_fault_delay = int_value(timings.get("post_fault_delay_seconds"), 30)

    run_dir = Path(args.out_dir).resolve() / f"{ts_compact()}_{name}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "experiment.yaml").write_text(experiment_path.read_text())
    print_status(f"starting experiment '{name}'")
    print_status(f"artifacts directory: {run_dir}")

    summary: Dict[str, Any] = {
        "name": str_value(config.get("name"), experiment_path.stem),
        "run_id": run_dir.name,
        "started_at_utc": utc_now(),
        "experiment_file": str(experiment_path),
        "namespace": namespace,
        "steps": {},
        "snapshots": {},
    }
    summary_path = run_dir / "summary.json"
    baseline_metrics_path = run_dir / "baseline_metrics.json"
    fault_metrics_path = run_dir / "fault_metrics.json"
    agent_report: Dict[str, Any] = {}
    evaluation: Dict[str, Any] = {}

    traffic_proc = None
    baseline_proc = None
    monitor_proc = None
    fault_active = False
    fault_cfg = config.get("fault", {}) or {}
    reset_cfg = config.get("reset", {}) or {}
    detector = config.get("detector", {}) or {}
    agent_cfg = config.get("agent", {}) or {}
    agent_type = str_value(agent_cfg.get("type"), "pipeline").strip().lower()
    prom_url = str_value(detector.get("prom_url"), "http://localhost:9090")
    jaeger_url = str_value(agent_cfg.get("jaeger_url"), "http://localhost:16686")
    benchmark_cfg = config.get("benchmark", {}) or {}
    benchmark_suite_path = Path(
        str_value(benchmark_cfg.get("suite_file"), str(DEFAULT_BENCHMARK_SUITE))
    ).resolve()
    benchmark_problem = resolve_problem_for_experiment(experiment_path, benchmark_suite_path)
    summary["benchmark_suite"] = str(benchmark_suite_path)
    summary["problem"] = benchmark_problem.to_dict() if benchmark_problem is not None else {}
    baseline_start_epoch = 0.0
    baseline_end_epoch = 0.0
    fault_start_epoch = 0.0
    fault_end_epoch = 0.0

    try:
        startup = config.get("startup", {}) or {}
        startup_enabled = bool_value(startup.get("enabled"), True) and not args.skip_startup
        summary["startup_effective_enabled"] = startup_enabled
        if startup_enabled:
            print_status("phase=startup: running start_all.sh")
            cmd = ["./scripts/start_all.sh", "-n", namespace]
            cmd.extend(list_value(startup.get("args")))
            summary["steps"]["startup"] = run_cmd(cmd, ROOT, run_dir / "startup.log")
            if summary["steps"]["startup"]["returncode"] != 0:
                raise RuntimeError("start_all.sh failed; see startup.log")
            print_status("phase=startup: completed")
        else:
            print_status("phase=startup: skipped")

        if bool_value(reset_cfg.get("enabled"), False) and bool_value(reset_cfg.get("before_run"), True):
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
                print_status("phase=reset: completed")
            else:
                summary["steps"]["reset_before"] = {
                    "skipped": True,
                    "reason": "cluster baseline already healthy",
                    "finished_at_utc": utc_now(),
                }
                print_status("phase=reset: skipped (cluster baseline already healthy)")

        verify_environment(namespace)
        print_status("phase=environment: verified")

        summary["steps"]["port_forward_prometheus"] = ensure_reusable_local_endpoint(
            namespace,
            "prometheus",
            prom_url,
            "/-/ready",
        )
        summary["steps"]["port_forward_jaeger"] = ensure_reusable_local_endpoint(
            namespace,
            "jaeger",
            jaeger_url,
            "/api/services",
        )

        print_status("phase=cleanup: removing lingering native fault resources")
        summary["steps"]["cleanup"] = cleanup_existing_native_faults(namespace, run_dir / "cleanup.log")
        print_status("phase=cleanup: completed")

        print_status("phase=snapshot: capturing before snapshot")
        summary["snapshots"]["before"] = capture_snapshot(namespace, "before", run_dir)
        print_status("phase=snapshot: before snapshot captured")

        traffic = config.get("traffic", {}) or {}
        frontend_base_url = str_value(traffic.get("base_url"), "http://localhost:8080")
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
            traffic_log = run_dir / "traffic.log"
            traffic_proc = start_process(traffic_cmd, ROOT, traffic_log)
            summary["steps"]["traffic"] = {
                "cmd": traffic_cmd,
                "pid": traffic_proc.pid,
                "log": rel_path(traffic_log),
                "started_at_utc": utc_now(),
            }
            print_status(
                "phase=traffic: started "
                f"(pid={traffic_proc.pid}, duration={traffic.get('duration_seconds', 300)}s, log={rel_path(traffic_log)})"
            )
        else:
            print_status("phase=traffic: skipped")

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
            baseline_log = run_dir / "baseline.log"
            baseline_proc = start_process(baseline_cmd, ROOT, baseline_log)
            summary["steps"]["baseline"] = {
                "cmd": baseline_cmd,
                "pid": baseline_proc.pid,
                "log": rel_path(baseline_log),
                "started_at_utc": utc_now(),
            }
            print_status(
                "phase=baseline: started "
                f"(pid={baseline_proc.pid}, duration={baseline.get('duration_seconds', 300)}s, log={rel_path(baseline_log)})"
            )
        else:
            print_status("phase=baseline: skipped")

        if bool_value(detector.get("enabled"), False):
            monitor_cmd = build_monitor_cmd(namespace, detector, run_dir)
            monitor_log = run_dir / "monitor.log"
            monitor_proc = start_process(
                monitor_cmd,
                ROOT,
                monitor_log,
                mirror_stdout=True,
                stdout_prefix="[monitor] ",
            )
            summary["steps"]["monitor"] = {
                "cmd": monitor_cmd,
                "pid": monitor_proc.pid,
                "log": rel_path(monitor_log),
                "started_at_utc": utc_now(),
            }
            print_status(
                "phase=monitor: started "
                f"(pid={monitor_proc.pid}, interval={detector.get('interval_seconds', 10)}s, log={rel_path(monitor_log)})"
            )
        else:
            print_status("phase=monitor: skipped")

        if bool_value(agent_cfg.get("enabled"), False):
            prewarm_started = utc_now()
            prewarm_agent_runtime(agent_cfg)
            summary["steps"]["agent_prewarm"] = {
                "provider": str_value(agent_cfg.get("provider"), os.environ.get("LLM_PROVIDER", "")),
                "model": str_value(
                    agent_cfg.get("model"),
                    os.environ.get("OLLAMA_MODEL", os.environ.get("OPENAI_MODEL", "")),
                ),
                "started_at_utc": prewarm_started,
                "finished_at_utc": utc_now(),
            }

        required_telemetry_services: List[str] = ["frontend"]
        if benchmark_problem is not None and benchmark_problem.target_service:
            required_telemetry_services.append(benchmark_problem.target_service)
        if benchmark_problem is not None:
            required_telemetry_services.extend(list(benchmark_problem.telemetry_contract.required_services))
        detector_target = str_value(detector.get("target_deployment"), "")
        if detector_target:
            required_telemetry_services.append(detector_target)
        required_telemetry_services = sorted({item for item in required_telemetry_services if item})
        print_status("phase=telemetry: validating observability sources")
        summary["steps"]["telemetry_validation"] = validate_telemetry_sources(
            namespace,
            prom_url,
            jaeger_url,
            run_dir,
            required_telemetry_services,
        )
        summary["steps"]["telemetry_contract"] = evaluate_telemetry_contract(
            benchmark_problem,
            summary["steps"]["telemetry_validation"],
        )
        if not bool(summary["steps"]["telemetry_contract"].get("ok", False)):
            raise RuntimeError("telemetry contract failed for this benchmark task; see telemetry_validation.log")
        if summary["steps"]["telemetry_validation"]["returncode"] != 0:
            print_status("phase=telemetry: validation had non-contract failures; continuing")
        print_status("phase=telemetry: validated")

        baseline_start_epoch = time.time()
        summary["baseline_window_start_utc"] = epoch_to_utc(baseline_start_epoch)
        sleep_with_progress(pre_fault_delay, "phase=pre_fault_delay")
        baseline_end_epoch = time.time()
        summary["baseline_window_end_utc"] = epoch_to_utc(baseline_end_epoch)

        if fault_cfg:
            fault_label = (
                str_value(fault_cfg.get("kind"))
                or str_value(fault_cfg.get("filepath"))
                or str_value(fault_cfg.get("scenario"), "fault")
            )
            print_status(
                "phase=fault_apply: applying "
                f"{fault_label}"
            )
            fault_start_epoch = time.time()
            summary["fault_window_start_utc"] = epoch_to_utc(fault_start_epoch)
            apply_cmd = build_fault_apply_cmd(namespace, fault_cfg)
            summary["steps"]["fault_apply"] = run_cmd(apply_cmd, ROOT, run_dir / "fault_apply.log")
            if summary["steps"]["fault_apply"]["returncode"] != 0:
                raise RuntimeError("fault apply failed; see fault_apply.log")
            fault_active = True
            print_status("phase=fault_apply: completed")
        else:
            print_status("phase=fault_apply: skipped")

        print_status("phase=snapshot: capturing during snapshot")
        summary["snapshots"]["during"] = capture_snapshot(namespace, "during", run_dir)
        print_status("phase=snapshot: during snapshot captured")

        if bool_value(agent_cfg.get("enabled"), False):
            if not bool_value(detector.get("enabled"), False):
                print_status("phase=agent: detector disabled, running agent immediately")
                detected = {}
            else:
                max_wait = int_value(agent_cfg.get("wait_for_incident_timeout_seconds"), 90)
                poll_interval = int_value(agent_cfg.get("wait_for_incident_poll_seconds"), 5)
                print_status(
                    f"phase=agent_wait: waiting up to {max_wait}s for detector incident confirmation"
                )
                detected = wait_for_incident(run_dir / "detector_runs", max_wait, poll_interval)

            if detected.get("incident_detected", False) or not bool_value(
                agent_cfg.get("require_incident_detected"), True
            ):
                if agent_type == "react":
                    print_status("phase=agent: running react agent")
                else:
                    print_status(
                        "phase=agent: running "
                        f"{str_value(agent_cfg.get('mode'), 'heuristic')} agent"
                    )
                ensure_ollama_model_available()
                seeded_detection_path = run_dir / "seeded_detection.json"
                seeded_detection_path.write_text(json.dumps(detected, indent=2))
                agent_cmd = build_agent_cmd(
                    namespace,
                    detector,
                    agent_cfg,
                    run_dir,
                    seeded_detection_path=seeded_detection_path,
                    benchmark_suite_path=benchmark_suite_path if benchmark_problem is not None else None,
                    problem=benchmark_problem,
                )
                summary["steps"]["agent"] = run_cmd_streaming(
                    agent_cmd,
                    ROOT,
                    run_dir / "agent.log",
                    stdout_prefix="[agent] ",
                )
                if summary["steps"]["agent"]["returncode"] != 0:
                    raise RuntimeError("agent run failed; see agent.log")
                agent_report = read_json_report(run_dir / "agent_report.json")
                evaluation = write_evaluation_artifact(
                    benchmark_problem,
                    agent_report,
                    run_dir / "evaluation.json",
                )
                summary["steps"]["evaluation"] = {
                    "file": rel_path(run_dir / "evaluation.json"),
                    "diagnosis_correct": evaluation.get("diagnosis_correct"),
                    "action_correct": evaluation.get("action_correct"),
                    "incident_detected": evaluation.get("incident_detected"),
                    "tool_calls_to_solution": evaluation.get("tool_calls_to_solution"),
                }
                summary["steps"]["agent"]["agent_type"] = agent_type
                summary["steps"]["agent"]["agent_variant"] = str_value(agent_report.get("agent_variant"), "react_diagnosis")
                verification = agent_report.get("verification") or {}
                if agent_type == "react":
                    solution = agent_report.get("solution") or {}
                    summary["steps"]["agent"]["recovered"] = False
                    summary["steps"]["agent"]["root_cause_mitigated"] = False
                    summary["steps"]["agent"]["submitted_solution"] = bool(solution)
                    summary["steps"]["agent"]["solution_root_cause"] = str(solution.get("root_cause", ""))
                    summary["steps"]["agent"]["solution_action"] = str(solution.get("action_taken", ""))
                    summary["steps"]["agent"]["recovery_summary"] = "react agent produced diagnosis only"
                    print_status(
                        "phase=agent: react agent produced diagnosis "
                        f"(root_cause='{solution.get('root_cause', '')}', action='{solution.get('action_taken', '')}')"
                    )
                elif verification.get("recovered", False):
                    fault_active = False
                    summary["steps"]["agent"]["recovered"] = True
                    summary["steps"]["agent"]["root_cause_mitigated"] = True
                    summary["steps"]["agent"]["recovery_summary"] = str(
                        verification.get("after_summary", "")
                    )
                    print_status(
                        "phase=agent: system recovered "
                        f"(summary='{verification.get('after_summary', '')}')"
                    )
                elif verification.get("root_cause_mitigated", False):
                    fault_active = False
                    summary["steps"]["agent"]["recovered"] = False
                    summary["steps"]["agent"]["root_cause_mitigated"] = True
                    summary["steps"]["agent"]["recovery_summary"] = str(
                        verification.get("after_summary", "")
                    )
                    print_status(
                        "phase=agent: root cause mitigated; user-facing symptoms still decaying "
                        f"(summary='{verification.get('after_summary', '')}')"
                    )
                else:
                    summary["steps"]["agent"]["recovered"] = False
                    summary["steps"]["agent"]["root_cause_mitigated"] = False
                    summary["steps"]["agent"]["recovery_summary"] = str(
                        verification.get("after_summary", "")
                    )
                    print_status(
                        "phase=agent: system not yet recovered "
                        f"(summary='{verification.get('after_summary', '')}')"
                    )
                print_status("phase=agent: completed")
            else:
                summary["steps"]["agent"] = {
                    "skipped": True,
                    "reason": "incident not detected before timeout",
                    "finished_at_utc": utc_now(),
                }
                evaluation = write_evaluation_artifact(
                    benchmark_problem,
                    {
                        "problem": benchmark_problem.to_dict() if benchmark_problem is not None else {},
                        "seeded_detection": detected,
                        "steps": [],
                        "solution": {},
                    },
                    run_dir / "evaluation.json",
                )
                summary["steps"]["evaluation"] = {
                    "file": rel_path(run_dir / "evaluation.json"),
                    "diagnosis_correct": evaluation.get("diagnosis_correct"),
                    "action_correct": evaluation.get("action_correct"),
                    "incident_detected": evaluation.get("incident_detected"),
                    "tool_calls_to_solution": evaluation.get("tool_calls_to_solution"),
                }
                print_status("phase=agent: skipped because no incident was detected before timeout")
        else:
            print_status("phase=agent: skipped")

        if fault_cfg:
            fault_duration = int_value(fault_cfg.get("duration_seconds"), 0)
            if fault_duration <= 0:
                raise RuntimeError("fault.duration_seconds must be a positive integer")
            sleep_with_progress(fault_duration, "phase=fault_duration")
            fault_end_epoch = time.time()
            summary["fault_window_end_utc"] = epoch_to_utc(fault_end_epoch)

        if baseline_start_epoch > 0 and baseline_end_epoch > baseline_start_epoch:
            baseline_metrics = collect_window_metrics(
                namespace,
                prom_url,
                baseline_start_epoch,
                baseline_end_epoch,
            )
            baseline_metrics_path.write_text(json.dumps(baseline_metrics, indent=2))
            summary["baseline_metrics_file"] = rel_path(baseline_metrics_path)
            print_status("phase=metrics: baseline metrics written")

        if fault_cfg and fault_start_epoch > 0 and fault_end_epoch > fault_start_epoch:
            fault_metrics = collect_window_metrics(
                namespace,
                prom_url,
                fault_start_epoch,
                fault_end_epoch,
            )
            fault_metrics_path.write_text(json.dumps(fault_metrics, indent=2))
            summary["fault_metrics_file"] = rel_path(fault_metrics_path)
            print_status("phase=metrics: fault metrics written")

        if fault_active:
            fault_label = (
                str_value(fault_cfg.get("kind"))
                or str_value(fault_cfg.get("filepath"))
                or str_value(fault_cfg.get("scenario"), "fault")
            )
            print_status(
                "phase=fault_revert: reverting "
                f"{fault_label}"
            )
            revert_cmd = build_fault_revert_cmd(namespace, fault_cfg)
            summary["steps"]["fault_revert"] = run_cmd(revert_cmd, ROOT, run_dir / "fault_revert.log")
            fault_active = False
            print_status("phase=fault_revert: completed")
        else:
            print_status("phase=fault_revert: skipped (fault already recovered or inactive)")

        sleep_with_progress(post_fault_delay, "phase=post_fault_delay")

        print_status("phase=snapshot: capturing after snapshot")
        summary["snapshots"]["after"] = capture_snapshot(namespace, "after", run_dir)
        print_status("phase=snapshot: after snapshot captured")

        if traffic_proc is not None:
            print_status("phase=traffic: waiting for traffic process to finish")
            summary["steps"]["traffic"]["returncode"] = finish_process(traffic_proc)
            summary["steps"]["traffic"]["finished_at_utc"] = utc_now()
            print_status(
                f"phase=traffic: finished with returncode={summary['steps']['traffic']['returncode']}"
            )
        if baseline_proc is not None:
            print_status("phase=baseline: waiting for baseline process to finish")
            summary["steps"]["baseline"]["returncode"] = finish_process(baseline_proc)
            summary["steps"]["baseline"]["finished_at_utc"] = utc_now()
            print_status(
                f"phase=baseline: finished with returncode={summary['steps']['baseline']['returncode']}"
            )
        if monitor_proc is not None:
            print_status("phase=monitor: stopping monitor process")
            summary["steps"]["monitor"]["returncode"] = terminate_process(monitor_proc)
            summary["steps"]["monitor"]["finished_at_utc"] = utc_now()
            print_status(
                f"phase=monitor: finished with returncode={summary['steps']['monitor']['returncode']}"
            )
        summary["result"] = "completed"
        summary["finished_at_utc"] = utc_now()
        if bool_value(reset_cfg.get("enabled"), False) and bool_value(reset_cfg.get("after_run"), True):
            summary["steps"]["reset_after_check"] = assess_reset_need(namespace)
            if summary["steps"]["reset_after_check"]["needs_reset"]:
                print_status("phase=reset_after: restoring cluster baseline")
                reset_cmd = build_reset_cmd(namespace, reset_cfg)
                summary["steps"]["reset_after"] = run_cmd_streaming(
                    reset_cmd,
                    ROOT,
                    run_dir / "reset_after.log",
                    stdout_prefix="[reset] ",
                )
                if summary["steps"]["reset_after"]["returncode"] != 0:
                    raise RuntimeError("cluster reset failed after run; see reset_after.log")
                print_status("phase=reset_after: completed")
            else:
                summary["steps"]["reset_after"] = {
                    "skipped": True,
                    "reason": "cluster baseline already healthy",
                    "finished_at_utc": utc_now(),
                }
                print_status("phase=reset_after: skipped (cluster baseline already healthy)")
        summary_path.write_text(json.dumps(summary, indent=2))
        write_episode_artifact(
            run_dir=run_dir,
            summary=summary,
            experiment_path=experiment_path,
            benchmark_suite_path=benchmark_suite_path,
            problem=benchmark_problem,
            config=config,
            agent_report=agent_report,
            evaluation=evaluation,
        )
        print_status("phase=complete: experiment finished successfully")
        print(f"Experiment complete. Artifacts: {run_dir}")
        return 0

    except Exception as exc:
        summary["result"] = "error"
        summary["error"] = str(exc)
        summary["finished_at_utc"] = utc_now()
        print_status(f"phase=error: {exc}")
        if fault_active:
            print_status("phase=fault_revert_on_error: reverting active fault")
            revert_cmd = build_fault_revert_cmd(namespace, fault_cfg)
            summary["steps"]["fault_revert_on_error"] = run_cmd(
                revert_cmd, ROOT, run_dir / "fault_revert_on_error.log"
            )
        if traffic_proc is not None:
            summary.setdefault("steps", {}).setdefault("traffic", {})["returncode"] = terminate_process(traffic_proc)
            summary["steps"]["traffic"]["finished_at_utc"] = utc_now()
        if baseline_proc is not None:
            summary.setdefault("steps", {}).setdefault("baseline", {})["returncode"] = terminate_process(baseline_proc)
            summary["steps"]["baseline"]["finished_at_utc"] = utc_now()
        if monitor_proc is not None:
            summary.setdefault("steps", {}).setdefault("monitor", {})["returncode"] = terminate_process(monitor_proc)
            summary["steps"]["monitor"]["finished_at_utc"] = utc_now()
        if bool_value(reset_cfg.get("enabled"), False) and bool_value(reset_cfg.get("on_error"), True):
            summary["steps"]["reset_on_error_check"] = assess_reset_need(namespace)
            if summary["steps"]["reset_on_error_check"]["needs_reset"]:
                print_status("phase=reset_on_error: restoring cluster baseline")
                reset_cmd = build_reset_cmd(namespace, reset_cfg)
                summary["steps"]["reset_on_error"] = run_cmd_streaming(
                    reset_cmd,
                    ROOT,
                    run_dir / "reset_on_error.log",
                    stdout_prefix="[reset] ",
                )
            else:
                summary["steps"]["reset_on_error"] = {
                    "skipped": True,
                    "reason": "cluster baseline already healthy",
                    "finished_at_utc": utc_now(),
                }
                print_status("phase=reset_on_error: skipped (cluster baseline already healthy)")
        summary_path.write_text(json.dumps(summary, indent=2))
        write_episode_artifact(
            run_dir=run_dir,
            summary=summary,
            experiment_path=experiment_path,
            benchmark_suite_path=benchmark_suite_path,
            problem=benchmark_problem,
            config=config,
            agent_report=agent_report,
            evaluation=evaluation,
        )
        print(f"Experiment failed. Artifacts: {run_dir}", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
