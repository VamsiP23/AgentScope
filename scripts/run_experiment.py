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
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = ROOT / "experiment_runs"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ts_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def require_binary(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"Required binary not found in PATH: {name}")


def rel_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except Exception:
        return str(path.resolve())


def run_cmd(cmd: List[str], cwd: Path, log_path: Path) -> Dict[str, Any]:
    started = utc_now()
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    log_path.write_text(
        "COMMAND: " + " ".join(shlex.quote(part) for part in cmd) + "\n\n"
        + "STDOUT:\n"
        + proc.stdout
        + "\nSTDERR:\n"
        + proc.stderr
    )
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "started_at_utc": started,
        "finished_at_utc": utc_now(),
        "log": rel_path(log_path),
    }


def start_process(cmd: List[str], cwd: Path, log_path: Path) -> subprocess.Popen[str]:
    handle = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=handle, stderr=subprocess.STDOUT, text=True)
    proc._agentscope_log_handle = handle  # type: ignore[attr-defined]
    return proc


def finish_process(proc: subprocess.Popen[str]) -> int:
    rc = proc.wait()
    handle = getattr(proc, "_agentscope_log_handle", None)
    if handle is not None:
        handle.close()
    return rc


def terminate_process(proc: subprocess.Popen[str]) -> int:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    handle = getattr(proc, "_agentscope_log_handle", None)
    if handle is not None:
        handle.close()
    return proc.returncode or 0


def load_yaml(path: Path) -> Dict[str, Any]:
    payload = yaml.safe_load(path.read_text())
    if not isinstance(payload, dict):
        raise RuntimeError(f"Experiment file must parse to a mapping: {path}")
    return payload


def bool_value(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise RuntimeError(f"Expected boolean value, got: {value!r}")


def int_value(value: Any, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    raise RuntimeError(f"Expected integer value, got: {value!r}")


def str_value(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    raise RuntimeError(f"Expected string value, got: {value!r}")


def list_value(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise RuntimeError(f"Expected list of strings, got: {value!r}")


def sanitize_name(name: str) -> str:
    cleaned = [ch.lower() if ch.isalnum() else "_" for ch in name]
    return "".join(cleaned).strip("_") or "experiment"


def build_fault_apply_cmd(namespace: str, fault: Dict[str, Any]) -> List[str]:
    scenario = str_value(fault.get("scenario"))
    if not scenario:
        raise RuntimeError("fault.scenario is required")

    cmd = ["./scripts/failure_inject.sh", "apply", scenario, "-n", namespace]
    target = str_value(fault.get("target"))
    latency = str_value(fault.get("latency"))
    auto_revert = bool_value(fault.get("auto_revert"), False)
    duration = int_value(fault.get("duration_seconds"), 0)

    if scenario == "service_outage" and target:
        cmd.extend(["-t", target])
    if scenario == "latency_spike" and latency:
        cmd.extend(["-l", latency])
    if auto_revert and duration > 0:
        cmd.extend(["-d", str(duration)])
    return cmd


def build_fault_revert_cmd(namespace: str, fault: Dict[str, Any]) -> List[str]:
    scenario = str_value(fault.get("scenario"))
    if not scenario:
        raise RuntimeError("fault.scenario is required")
    cmd = ["./scripts/failure_inject.sh", "revert", scenario, "-n", namespace]
    target = str_value(fault.get("target"))
    if scenario == "service_outage" and target:
        cmd.extend(["-t", target])
    return cmd


def build_monitor_cmd(namespace: str, detector: Dict[str, Any], run_dir: Path) -> List[str]:
    cmd = [
        "./scripts/monitor_loop.py",
        "--namespace",
        namespace,
        "--prom-url",
        str_value(detector.get("prom_url"), "http://localhost:9090"),
        "--window",
        str_value(detector.get("window"), "1m"),
        "--target-deployment",
        str_value(detector.get("target_deployment"), ""),
        "--error-ratio-threshold",
        str(detector.get("error_ratio_threshold", 0.10)),
        "--service-error-rps-threshold",
        str(detector.get("service_error_rps_threshold", 0.50)),
        "--min-total-rps",
        str(detector.get("min_total_rps", 0.10)),
        "--restart-count-threshold",
        str(int_value(detector.get("restart_count_threshold"), 1)),
        "--out-dir",
        str(run_dir / "detector_runs"),
        "--interval-seconds",
        str(int_value(detector.get("interval_seconds"), 10)),
    ]
    return cmd


def capture_snapshot(namespace: str, label: str, out_dir: Path) -> Dict[str, Any]:
    snapshots = {}
    commands = {
        f"{label}_deployments.txt": ["kubectl", "get", "deploy", "-n", namespace],
        f"{label}_pods.txt": ["kubectl", "get", "pods", "-n", namespace],
        f"{label}_events.txt": [
            "kubectl",
            "get",
            "events",
            "-n",
            namespace,
            "--sort-by=.metadata.creationTimestamp",
        ],
    }
    for filename, cmd in commands.items():
        snapshots[filename] = run_cmd(cmd, ROOT, out_dir / filename)
    return snapshots


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an experiment from a YAML file.")
    parser.add_argument("experiment_file", help="Path to experiment YAML file")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Run artifact root")
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

    traffic_proc = None
    baseline_proc = None
    monitor_proc = None
    fault_active = False
    fault_cfg = config.get("fault", {}) or {}

    try:
        startup = config.get("startup", {}) or {}
        if bool_value(startup.get("enabled"), True):
            cmd = ["./scripts/start_all.sh", "-n", namespace]
            cmd.extend(list_value(startup.get("args")))
            summary["steps"]["startup"] = run_cmd(cmd, ROOT, run_dir / "startup.log")
            if summary["steps"]["startup"]["returncode"] != 0:
                raise RuntimeError("start_all.sh failed; see startup.log")

        summary["snapshots"]["before"] = capture_snapshot(namespace, "before", run_dir)

        traffic = config.get("traffic", {}) or {}
        if bool_value(traffic.get("enabled"), False):
            traffic_cmd = [
                "./scripts/generate_traffic.sh",
                "-u",
                str_value(traffic.get("base_url"), "http://localhost:8080"),
                "-d",
                str(int_value(traffic.get("duration_seconds"), 300)),
                "-r",
                str(int_value(traffic.get("rps"), 1)),
            ]
            traffic_log = run_dir / "traffic.log"
            traffic_proc = start_process(traffic_cmd, ROOT, traffic_log)
            summary["steps"]["traffic"] = {
                "cmd": traffic_cmd,
                "pid": traffic_proc.pid,
                "log": rel_path(traffic_log),
                "started_at_utc": utc_now(),
            }

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

        detector = config.get("detector", {}) or {}
        if bool_value(detector.get("enabled"), False):
            monitor_cmd = build_monitor_cmd(namespace, detector, run_dir)
            monitor_log = run_dir / "monitor.log"
            monitor_proc = start_process(monitor_cmd, ROOT, monitor_log)
            summary["steps"]["monitor"] = {
                "cmd": monitor_cmd,
                "pid": monitor_proc.pid,
                "log": rel_path(monitor_log),
                "started_at_utc": utc_now(),
            }

        if pre_fault_delay > 0:
            time.sleep(pre_fault_delay)

        if fault_cfg:
            apply_cmd = build_fault_apply_cmd(namespace, fault_cfg)
            summary["steps"]["fault_apply"] = run_cmd(apply_cmd, ROOT, run_dir / "fault_apply.log")
            if summary["steps"]["fault_apply"]["returncode"] != 0:
                raise RuntimeError("fault apply failed; see fault_apply.log")
            fault_active = not bool_value(fault_cfg.get("auto_revert"), False)

        summary["snapshots"]["during"] = capture_snapshot(namespace, "during", run_dir)

        if post_fault_delay > 0:
            time.sleep(post_fault_delay)

        if fault_active:
            revert_cmd = build_fault_revert_cmd(namespace, fault_cfg)
            summary["steps"]["fault_revert"] = run_cmd(revert_cmd, ROOT, run_dir / "fault_revert.log")
            fault_active = False

        summary["snapshots"]["after"] = capture_snapshot(namespace, "after", run_dir)

        if traffic_proc is not None:
            summary["steps"]["traffic"]["returncode"] = finish_process(traffic_proc)
            summary["steps"]["traffic"]["finished_at_utc"] = utc_now()
        if baseline_proc is not None:
            summary["steps"]["baseline"]["returncode"] = finish_process(baseline_proc)
            summary["steps"]["baseline"]["finished_at_utc"] = utc_now()
        if monitor_proc is not None:
            summary["steps"]["monitor"]["returncode"] = terminate_process(monitor_proc)
            summary["steps"]["monitor"]["finished_at_utc"] = utc_now()

        summary["result"] = "completed"
        summary["finished_at_utc"] = utc_now()
        summary_path.write_text(json.dumps(summary, indent=2))
        print(f"Experiment complete. Artifacts: {run_dir}")
        return 0

    except Exception as exc:
        summary["result"] = "error"
        summary["error"] = str(exc)
        summary["finished_at_utc"] = utc_now()
        if fault_active:
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
        summary_path.write_text(json.dumps(summary, indent=2))
        print(f"Experiment failed. Artifacts: {run_dir}", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
