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
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlencode
from urllib.request import urlopen

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


def print_status(message: str) -> None:
    print(f"[{utc_now()}] {message}", flush=True)


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


def run_cmd_streaming(
    cmd: List[str],
    cwd: Path,
    log_path: Path,
    *,
    stdout_prefix: str = "",
) -> Dict[str, Any]:
    started = utc_now()
    with open(log_path, "w", encoding="utf-8") as handle:
        handle.write("COMMAND: " + " ".join(shlex.quote(part) for part in cmd) + "\n\n")
        handle.write("STREAMED OUTPUT:\n")
        handle.flush()
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            handle.write(line)
            handle.flush()
            sys.stdout.write(f"{stdout_prefix}{line}")
            sys.stdout.flush()
        proc.stdout.close()
        returncode = proc.wait()
    return {
        "cmd": cmd,
        "returncode": returncode,
        "started_at_utc": started,
        "finished_at_utc": utc_now(),
        "log": rel_path(log_path),
    }


def _stream_output(
    proc: subprocess.Popen[str],
    handle: Any,
    prefix: str,
    mirror_stdout: bool,
) -> None:
    if proc.stdout is None:
        return
    try:
        for line in proc.stdout:
            handle.write(line)
            handle.flush()
            if mirror_stdout:
                sys.stdout.write(f"{prefix}{line}")
                sys.stdout.flush()
    finally:
        proc.stdout.close()


def start_process(
    cmd: List[str],
    cwd: Path,
    log_path: Path,
    *,
    mirror_stdout: bool = False,
    stdout_prefix: str = "",
) -> subprocess.Popen[str]:
    handle = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    proc._agentscope_log_handle = handle  # type: ignore[attr-defined]
    stream_thread = threading.Thread(
        target=_stream_output,
        args=(proc, handle, stdout_prefix, mirror_stdout),
        daemon=True,
    )
    stream_thread.start()
    proc._agentscope_stream_thread = stream_thread  # type: ignore[attr-defined]
    return proc


def finish_process(proc: subprocess.Popen[str]) -> int:
    rc = proc.wait()
    stream_thread = getattr(proc, "_agentscope_stream_thread", None)
    if stream_thread is not None:
        stream_thread.join(timeout=2)
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
    stream_thread = getattr(proc, "_agentscope_stream_thread", None)
    if stream_thread is not None:
        stream_thread.join(timeout=2)
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


def epoch_to_utc(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sleep_with_progress(total_seconds: int, label: str) -> None:
    if total_seconds <= 0:
        return

    print_status(f"{label}: waiting {total_seconds}s")
    remaining = total_seconds
    step = 10 if total_seconds > 30 else 5 if total_seconds > 10 else 1
    while remaining > 0:
        chunk = min(step, remaining)
        time.sleep(chunk)
        remaining -= chunk
        if remaining > 0:
            print_status(f"{label}: {remaining}s remaining")
    print_status(f"{label}: done")


def build_fault_apply_cmd(namespace: str, fault: Dict[str, Any]) -> List[str]:
    filepath = str_value(fault.get("filepath"))
    if not filepath:
        raise RuntimeError("fault.filepath is required")

    fault_path = Path(filepath)
    if not fault_path.is_absolute():
        fault_path = (ROOT / fault_path).resolve()

    return ["python3", "-m", "faults.cli", "apply", str(fault_path)]


def build_fault_revert_cmd(namespace: str, fault: Dict[str, Any]) -> List[str]:
    filepath = str_value(fault.get("filepath"))
    if not filepath:
        raise RuntimeError("fault.filepath is required")

    fault_path = Path(filepath)
    if not fault_path.is_absolute():
        fault_path = (ROOT / fault_path).resolve()

    return ["python3", "-m", "faults.cli", "revert", str(fault_path)]


def prom_query(prom_url: str, query: str, eval_time: float | None = None) -> Dict[str, Any]:
    params: Dict[str, str] = {"query": query}
    if eval_time is not None:
        params["time"] = str(eval_time)
    url = f"{prom_url.rstrip('/')}/api/v1/query?{urlencode(params)}"
    with urlopen(url, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus query failed: {payload}")
    return payload.get("data", {})


def prom_vector_map(
    prom_url: str,
    query: str,
    *,
    key: str,
    eval_time: float,
) -> Dict[str, float]:
    data = prom_query(prom_url, query, eval_time=eval_time)
    rows = data.get("result", [])
    parsed: Dict[str, float] = {}
    for row in rows:
        item_key = row.get("metric", {}).get(key)
        if not item_key:
            continue
        try:
            parsed[item_key] = float(row.get("value", [0, "0"])[1])
        except (TypeError, ValueError):
            parsed[item_key] = 0.0
    return parsed


def prometheus_service_metrics(
    prom_url: str,
    window_seconds: int,
    eval_time: float,
) -> Dict[str, Dict[str, Any]]:
    window = f"{max(1, window_seconds)}s"
    request_totals = prom_vector_map(
        prom_url,
        f"sum(increase(calls_total[{window}])) by (service_name)",
        key="service_name",
        eval_time=eval_time,
    )
    error_totals = prom_vector_map(
        prom_url,
        f'sum(increase(calls_total{{status_code="STATUS_CODE_ERROR"}}[{window}])) by (service_name)',
        key="service_name",
        eval_time=eval_time,
    )

    p99_latency: Dict[str, float] = {}
    latency_queries = [
        f"histogram_quantile(0.99, sum(increase(duration_milliseconds_bucket[{window}])) by (service_name, le))",
        f"histogram_quantile(0.99, sum(increase(duration_bucket[{window}])) by (service_name, le))",
        f"histogram_quantile(0.99, sum(increase(latency_bucket[{window}])) by (service_name, le))",
    ]
    for latency_query in latency_queries:
        rows = prom_vector_map(prom_url, latency_query, key="service_name", eval_time=eval_time)
        if rows:
            p99_latency = rows
            break

    cpu_by_pod = prom_vector_map(
        prom_url,
        (
            f"1000 * sum(increase(container_cpu_usage_seconds_total{{namespace=\"default\",pod!=\"\"}}[{window}])) "
            f"by (pod) / {max(1, window_seconds)}"
        ),
        key="pod",
        eval_time=eval_time,
    )
    memory_by_pod = prom_vector_map(
        prom_url,
        (
            f"avg by (pod) (avg_over_time(container_memory_working_set_bytes{{namespace=\"default\",pod!=\"\"}}[{window}])) "
            "/ 1048576"
        ),
        key="pod",
        eval_time=eval_time,
    )

    services = sorted(set(request_totals) | set(error_totals) | set(p99_latency))
    result: Dict[str, Dict[str, Any]] = {}
    for service in services:
        total = request_totals.get(service, 0.0)
        errors = error_totals.get(service, 0.0)
        result[service] = {
            "request_rate_rps": total / max(1, window_seconds),
            "error_percentage": (errors / total * 100.0) if total > 0 else 0.0,
            "p99_latency_ms": p99_latency.get(service),
        }

    return {
        "services": result,
        "pod_cpu_millicores": cpu_by_pod,
        "pod_memory_mib": memory_by_pod,
    }


def kubectl_json(cmd: List[str]) -> Dict[str, Any]:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip() or "kubectl command failed"
        raise RuntimeError(err)
    return json.loads(proc.stdout)


def kubernetes_snapshot_metrics(namespace: str) -> Dict[str, Any]:
    deployments_payload = kubectl_json(["kubectl", "get", "deploy", "-n", namespace, "-o", "json"])
    pods_payload = kubectl_json(["kubectl", "get", "pods", "-n", namespace, "-o", "json"])

    deployments: Dict[str, Any] = {}
    for item in deployments_payload.get("items", []):
        name = item.get("metadata", {}).get("name")
        if not name:
            continue
        deployments[name] = {
            "desired": int(item.get("spec", {}).get("replicas", 0) or 0),
            "available": int(item.get("status", {}).get("availableReplicas", 0) or 0),
            "ready": int(item.get("status", {}).get("readyReplicas", 0) or 0),
            "updated": int(item.get("status", {}).get("updatedReplicas", 0) or 0),
        }

    services: Dict[str, Dict[str, Any]] = {}
    for item in pods_payload.get("items", []):
        metadata = item.get("metadata", {})
        labels = metadata.get("labels", {}) or {}
        service = labels.get("app")
        pod_name = metadata.get("name")
        if not service or not pod_name:
            continue
        pod_phase = item.get("status", {}).get("phase", "Unknown")
        pod_record = {
            "name": pod_name,
            "phase": pod_phase,
            "node": item.get("spec", {}).get("nodeName"),
            "pod_ip": item.get("status", {}).get("podIP"),
        }
        services.setdefault(service, {"active_pods": 0, "pods": []})
        if pod_phase == "Running":
            services[service]["active_pods"] += 1
        services[service]["pods"].append(pod_record)

    return {
        "services": services,
        "deployments": deployments,
    }


def collect_window_metrics(
    namespace: str,
    prom_url: str,
    start_epoch: float,
    end_epoch: float,
) -> Dict[str, Any]:
    window_seconds = max(1, int(end_epoch - start_epoch))
    prom = prometheus_service_metrics(prom_url, window_seconds, end_epoch)
    k8s = kubernetes_snapshot_metrics(namespace)

    services = sorted(
        set(prom["services"].keys())
        | set(k8s["services"].keys())
        | set(k8s["deployments"].keys())
    )

    output_services: Dict[str, Any] = {}
    for service in services:
        pod_entries = k8s["services"].get(service, {}).get("pods", [])
        output_services[service] = {
            "p99_latency_ms": prom["services"].get(service, {}).get("p99_latency_ms"),
            "error_percentage": prom["services"].get(service, {}).get("error_percentage", 0.0),
            "request_rate_rps": prom["services"].get(service, {}).get("request_rate_rps", 0.0),
            "active_pods": k8s["services"].get(service, {}).get("active_pods", 0),
            "deployment_health": k8s["deployments"].get(service),
            "pods": [
                {
                    **pod,
                    "cpu_millicores": prom["pod_cpu_millicores"].get(pod["name"]),
                    "memory_mib": prom["pod_memory_mib"].get(pod["name"]),
                }
                for pod in pod_entries
            ],
        }

    return {
        "window": {
            "start_utc": epoch_to_utc(start_epoch),
            "end_utc": epoch_to_utc(end_epoch),
            "duration_seconds": window_seconds,
        },
        "services": output_services,
    }


def verify_environment(namespace: str) -> None:
    required = [
        "frontend",
        "prometheus",
        "jaeger",
        "opentelemetrycollector",
    ]
    deployments_payload = kubectl_json(["kubectl", "get", "deploy", "-n", namespace, "-o", "json"])
    available = {
        item.get("metadata", {}).get("name"): int(item.get("status", {}).get("availableReplicas", 0) or 0)
        for item in deployments_payload.get("items", [])
    }
    missing = [name for name in required if available.get(name, 0) < 1]
    if missing:
        raise RuntimeError(f"required deployments unavailable in namespace {namespace}: {', '.join(missing)}")


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
        "--service-latency-threshold-ms",
        str(detector.get("service_latency_threshold_ms", 1000.0)),
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


def build_agent_cmd(
    namespace: str,
    detector: Dict[str, Any],
    agent: Dict[str, Any],
    run_dir: Path,
    seeded_detection_path: Path | None = None,
) -> List[str]:
    cmd = [
        "./scripts/run_agent.py",
        "--namespace",
        namespace,
        "--prom-url",
        str_value(detector.get("prom_url"), "http://localhost:9090"),
        "--jaeger-url",
        str_value(agent.get("jaeger_url"), "http://localhost:16686"),
        "--window",
        str_value(detector.get("window"), "1m"),
        "--target-deployment",
        str_value(agent.get("target_deployment"), str_value(detector.get("target_deployment"), "")),
        "--error-ratio-threshold",
        str(detector.get("error_ratio_threshold", 0.10)),
        "--service-error-rps-threshold",
        str(detector.get("service_error_rps_threshold", 0.50)),
        "--service-latency-threshold-ms",
        str(detector.get("service_latency_threshold_ms", 1000.0)),
        "--min-total-rps",
        str(detector.get("min_total_rps", 0.10)),
        "--restart-count-threshold",
        str(int_value(detector.get("restart_count_threshold"), 1)),
        "--mode",
        str_value(agent.get("mode"), "heuristic"),
        "--max-iterations",
        str(int_value(agent.get("max_iterations"), 2)),
        "--research-max-tool-calls",
        str(int_value(agent.get("research_max_tool_calls"), 5)),
        "--verify-wait-seconds",
        str(int_value(agent.get("verify_wait_seconds"), 30)),
        "--seed-detection-file",
        str(seeded_detection_path) if seeded_detection_path is not None else "",
        "--out-file",
        str(run_dir / "agent_report.json"),
    ]
    if bool_value(agent.get("dry_run"), True):
        cmd.append("--dry-run")
    return cmd


def ensure_ollama_model_available() -> None:
    provider = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if provider != "ollama":
        return

    require_binary("ollama")
    model = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b").strip()
    if not model:
        raise RuntimeError("OLLAMA_MODEL must be set when LLM_PROVIDER=ollama")

    show_proc = subprocess.run(
        ["ollama", "show", model],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if show_proc.returncode == 0:
        print_status(f"phase=agent: ollama model ready ({model})")
        return

    print_status(f"phase=agent: pulling missing ollama model ({model})")
    pull_proc = subprocess.run(
        ["ollama", "pull", model],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if pull_proc.returncode != 0:
        raise RuntimeError(
            "failed to pull ollama model "
            f"{model}: {pull_proc.stderr.strip() or pull_proc.stdout.strip() or 'unknown error'}"
        )
    print_status(f"phase=agent: ollama model pulled ({model})")


def read_detection_report(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def read_json_report(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def wait_for_incident(detector_runs_dir: Path, max_wait_seconds: int, poll_interval: int) -> Dict[str, Any]:
    latest_path = detector_runs_dir / "latest_detection.json"
    deadline = time.time() + max_wait_seconds
    last_summary = ""
    while time.time() <= deadline:
        report = read_detection_report(latest_path)
        if report:
            summary = str(report.get("summary", ""))
            if summary and summary != last_summary:
                print_status(f"phase=agent_wait: detector summary='{summary}'")
                last_summary = summary
            if report.get("incident_detected", False):
                return report
        time.sleep(max(1, poll_interval))
    return read_detection_report(latest_path)


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

    traffic_proc = None
    baseline_proc = None
    monitor_proc = None
    fault_active = False
    fault_cfg = config.get("fault", {}) or {}
    detector = config.get("detector", {}) or {}
    agent_cfg = config.get("agent", {}) or {}
    prom_url = str_value(detector.get("prom_url"), "http://localhost:9090")
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

        verify_environment(namespace)
        print_status("phase=environment: verified")

        print_status("phase=snapshot: capturing before snapshot")
        summary["snapshots"]["before"] = capture_snapshot(namespace, "before", run_dir)
        print_status("phase=snapshot: before snapshot captured")

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

        baseline_start_epoch = time.time()
        summary["baseline_window_start_utc"] = epoch_to_utc(baseline_start_epoch)
        sleep_with_progress(pre_fault_delay, "phase=pre_fault_delay")
        baseline_end_epoch = time.time()
        summary["baseline_window_end_utc"] = epoch_to_utc(baseline_end_epoch)

        if fault_cfg:
            fault_label = str_value(fault_cfg.get("filepath")) or str_value(fault_cfg.get("scenario"), "fault")
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
                verification = agent_report.get("verification") or {}
                if verification.get("recovered", False):
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
            fault_label = str_value(fault_cfg.get("filepath")) or str_value(fault_cfg.get("scenario"), "fault")
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
        summary_path.write_text(json.dumps(summary, indent=2))
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
        summary_path.write_text(json.dumps(summary, indent=2))
        print(f"Experiment failed. Artifacts: {run_dir}", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
