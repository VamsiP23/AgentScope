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
from urllib.parse import urlencode, urlparse
from urllib.request import urlopen

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from benchmarking.evaluator import evaluate_agent_run
from benchmarking.problem import ProblemSpec, resolve_problem_for_experiment

DEFAULT_OUT_DIR = ROOT / "experiment_runs"
DEFAULT_BENCHMARK_SUITE = ROOT / "benchmark_suite.yaml"
SESSION_PORT_FORWARD_DIR = ROOT / ".runtime" / "port_forwards"
CORE_DEPLOYMENTS = [
    "frontend",
    "cartservice",
    "checkoutservice",
    "currencyservice",
    "productcatalogservice",
    "recommendationservice",
    "shippingservice",
    "paymentservice",
    "emailservice",
    "adservice",
    "redis-cart",
    "opentelemetrycollector",
    "kube-state-metrics",
    "jaeger",
    "prometheus",
    "grafana",
]
CHAOS_RESOURCE_TYPES = [
    "podchaos",
    "stresschaos",
    "networkchaos",
    "dnschaos",
    "httpchaos",
]


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


def endpoint_reachable(url: str, *, probe_path: str = "", timeout_seconds: int = 5) -> bool:
    target = url.rstrip("/")
    if probe_path:
        target = f"{target}{probe_path}"
    try:
        with urlopen(target, timeout=timeout_seconds):
            return True
    except Exception:
        return False


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
    apply_cmd = list_value(fault.get("apply_cmd"))
    if apply_cmd:
        return apply_cmd

    filepath = str_value(fault.get("filepath"))
    if not filepath:
        raise RuntimeError("fault.filepath or fault.apply_cmd is required")

    fault_path = Path(filepath)
    if not fault_path.is_absolute():
        fault_path = (ROOT / fault_path).resolve()

    return ["python3", "-m", "faults.cli", "apply", str(fault_path)]


def build_fault_revert_cmd(namespace: str, fault: Dict[str, Any]) -> List[str]:
    revert_cmd = list_value(fault.get("revert_cmd"))
    if revert_cmd:
        return revert_cmd

    filepath = str_value(fault.get("filepath"))
    if not filepath:
        raise RuntimeError("fault.filepath or fault.revert_cmd is required")

    fault_path = Path(filepath)
    if not fault_path.is_absolute():
        fault_path = (ROOT / fault_path).resolve()

    return ["python3", "-m", "faults.cli", "revert", str(fault_path)]


def build_reset_cmd(namespace: str, reset_cfg: Dict[str, Any]) -> List[str]:
    cmd = ["./scripts/reset_cluster.sh", "-n", namespace]
    context = str_value(reset_cfg.get("context"))
    manifest = str_value(reset_cfg.get("manifest"))
    if context:
        cmd.extend(["-c", context])
    if manifest:
        cmd.extend(["-m", manifest])
    if bool_value(reset_cfg.get("kill_port_forwards"), False):
        cmd.append("-p")
    if bool_value(reset_cfg.get("refresh_observability"), False):
        cmd.append("-o")
    cmd.extend(list_value(reset_cfg.get("args")))
    return cmd


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


def kubectl_run(cmd: List[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)


def kubectl_lines_or_empty(cmd: List[str]) -> List[str]:
    proc = kubectl_run(cmd)
    if proc.returncode != 0:
        stderr = (proc.stderr or "").lower()
        stdout = (proc.stdout or "").lower()
        # Some clusters may not have every Chaos Mesh CRD installed.
        if "the server doesn't have a resource type" in stderr or "notfound" in stderr:
            return []
        if "the server doesn't have a resource type" in stdout or "notfound" in stdout:
            return []
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "kubectl command failed")
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


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
        "kube-state-metrics",
    ]
    deployments_payload = kubectl_json(["kubectl", "get", "deploy", "-n", namespace, "-o", "json"])
    available = {
        item.get("metadata", {}).get("name"): int(item.get("status", {}).get("availableReplicas", 0) or 0)
        for item in deployments_payload.get("items", [])
    }
    missing = [name for name in required if available.get(name, 0) < 1]
    if missing:
        raise RuntimeError(f"required deployments unavailable in namespace {namespace}: {', '.join(missing)}")


def verify_chaos_mesh_health() -> None:
    controller = kubectl_json(
        ["kubectl", "get", "deploy", "chaos-controller-manager", "-n", "chaos-mesh", "-o", "json"]
    )
    desired = int(controller.get("spec", {}).get("replicas", 0) or 0)
    available = int(controller.get("status", {}).get("availableReplicas", 0) or 0)
    ready = int(controller.get("status", {}).get("readyReplicas", 0) or 0)
    if desired < 1 or available < 1 or ready < 1:
        raise RuntimeError(
            "Chaos Mesh controller is not healthy: "
            f"desired={desired} available={available} ready={ready}"
        )

    endpoints = kubectl_json(
        ["kubectl", "get", "endpoints", "chaos-mesh-controller-manager", "-n", "chaos-mesh", "-o", "json"]
    )
    subsets = endpoints.get("subsets") or []
    addresses = sum(len(subset.get("addresses") or []) for subset in subsets)
    ports = sum(len(subset.get("ports") or []) for subset in subsets)
    if addresses < 1 or ports < 1:
        raise RuntimeError(
            "Chaos Mesh webhook service has no ready endpoints; "
            f"addresses={addresses} ports={ports}"
        )


def list_existing_chaos_objects(namespace: str) -> List[str]:
    existing: List[str] = []
    for resource in CHAOS_RESOURCE_TYPES:
        existing.extend(
            kubectl_lines_or_empty(
                ["kubectl", "get", resource, "-n", namespace, "-o", "name"]
            )
        )
    return existing


def cleanup_existing_chaos(namespace: str, log_path: Path) -> Dict[str, Any]:
    existing = list_existing_chaos_objects(namespace)
    log_lines = [
        f"timestamp_utc: {utc_now()}",
        f"namespace: {namespace}",
        f"found: {len(existing)}",
    ]
    if existing:
        log_lines.append("existing_objects:")
        log_lines.extend(f"  - {name}" for name in existing)
    else:
        log_lines.append("existing_objects: []")

    deleted: List[str] = []
    for resource in CHAOS_RESOURCE_TYPES:
        names = kubectl_lines_or_empty(["kubectl", "get", resource, "-n", namespace, "-o", "name"])
        if not names:
            continue
        proc = kubectl_run(
            ["kubectl", "delete", resource, "--all", "-n", namespace, "--ignore-not-found", "--timeout=120s"]
        )
        log_lines.append("")
        log_lines.append("COMMAND: " + " ".join(shlex.quote(part) for part in proc.args))
        log_lines.append("STDOUT:")
        log_lines.append(proc.stdout.rstrip())
        log_lines.append("STDERR:")
        log_lines.append(proc.stderr.rstrip())
        if proc.returncode != 0:
            log_path.write_text("\n".join(log_lines) + "\n")
            raise RuntimeError(
                proc.stderr.strip() or proc.stdout.strip() or f"failed to delete existing {resource}"
            )
        deleted.extend(names)

    deadline = time.time() + 60
    while deleted and time.time() < deadline:
        remaining = list_existing_chaos_objects(namespace)
        if not remaining:
            break
        time.sleep(2)

    remaining = list_existing_chaos_objects(namespace)
    log_lines.append("")
    log_lines.append(f"deleted: {len(deleted)}")
    if deleted:
        log_lines.extend(f"  - {name}" for name in deleted)
    else:
        log_lines.append("deleted_objects: []")
    log_lines.append(f"remaining: {len(remaining)}")
    if remaining:
        log_lines.extend(f"  - {name}" for name in remaining)
    log_path.write_text("\n".join(log_lines) + "\n")

    if remaining:
        raise RuntimeError(
            "stale Chaos Mesh resources still present in namespace "
            f"{namespace}: {', '.join(remaining)}"
        )

    return {
        "found": len(existing),
        "deleted": deleted,
        "remaining": remaining,
        "log": rel_path(log_path),
        "finished_at_utc": utc_now(),
    }


def unhealthy_core_deployments(namespace: str) -> List[Dict[str, Any]]:
    deployments_payload = kubectl_json(["kubectl", "get", "deploy", "-n", namespace, "-o", "json"])
    items = {str(item.get("metadata", {}).get("name", "")): item for item in deployments_payload.get("items", [])}
    unhealthy: List[Dict[str, Any]] = []
    for name in CORE_DEPLOYMENTS:
        item = items.get(name)
        if item is None:
            continue
        desired = int(item.get("spec", {}).get("replicas", 0) or 0)
        available = int(item.get("status", {}).get("availableReplicas", 0) or 0)
        ready = int(item.get("status", {}).get("readyReplicas", 0) or 0)
        if available < desired or ready < desired:
            unhealthy.append(
                {
                    "deployment": name,
                    "desired": desired,
                    "available": available,
                    "ready": ready,
                }
            )
    return unhealthy


def assess_reset_need(namespace: str) -> Dict[str, Any]:
    reasons: List[str] = []
    details: Dict[str, Any] = {}

    try:
        stale_chaos = list_existing_chaos_objects(namespace)
    except Exception as exc:
        stale_chaos = []
        reasons.append(f"failed to inspect chaos resources: {exc}")
    if stale_chaos:
        reasons.append(f"found {len(stale_chaos)} lingering chaos resources")
        details["stale_chaos_resources"] = stale_chaos

    try:
        unhealthy = unhealthy_core_deployments(namespace)
    except Exception as exc:
        unhealthy = []
        reasons.append(f"failed to inspect core deployments: {exc}")
    if unhealthy:
        reasons.append("one or more core deployments are unavailable")
        details["unhealthy_deployments"] = unhealthy

    try:
        verify_environment(namespace)
    except Exception as exc:
        reasons.append(f"environment verification failed: {exc}")

    try:
        verify_chaos_mesh_health()
    except Exception as exc:
        reasons.append(f"chaos mesh health check failed: {exc}")

    return {
        "needs_reset": bool(reasons),
        "reasons": reasons,
        "details": details,
        "checked_at_utc": utc_now(),
    }


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
        "--latency-consecutive-required",
        str(int_value(detector.get("latency_consecutive_required"), 2)),
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
    benchmark_suite_path: Path | None = None,
    problem: ProblemSpec | None = None,
) -> List[str]:
    agent_type = str_value(agent.get("type"), "pipeline").strip().lower()
    if agent_type == "react":
        cmd = [
            "python3",
            "./scripts/run_react_agent.py",
            "--namespace",
            namespace,
            "--prom-url",
            str_value(detector.get("prom_url"), "http://localhost:9090"),
            "--jaeger-url",
            str_value(agent.get("jaeger_url"), "http://localhost:16686"),
            "--target-deployment",
            str_value(agent.get("target_deployment"), str_value(detector.get("target_deployment"), "")),
            "--problem-description",
            str_value(
                agent.get("problem_description"),
                (
                    "An incident has been detected in the Online Boutique cluster. "
                    "Investigate using available tools and identify the root cause and appropriate remediation action."
                ),
            ),
            "--jaeger-enabled",
            "true" if bool_value(agent.get("jaeger_enabled"), True) else "false",
            "--max-steps",
            str(int_value(agent.get("max_steps"), 35)),
            "--seed-detection-file",
            str(seeded_detection_path) if seeded_detection_path is not None else "",
            "--out-file",
            str(run_dir / "agent_report.json"),
        ]
        provider = str_value(agent.get("provider"), "")
        model = str_value(agent.get("model"), "")
        if provider:
            cmd.extend(["--provider", provider])
        if model:
            cmd.extend(["--model", model])
        if bool_value(agent.get("dry_run"), True):
            cmd.append("--dry-run")
        if benchmark_suite_path is not None and problem is not None:
            cmd.extend(["--benchmark-suite", str(benchmark_suite_path)])
            cmd.extend(["--problem-id", problem.problem_id])
        return cmd

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


def _managed_port_forward_paths(service_name: str) -> tuple[Path, Path]:
    return (
        SESSION_PORT_FORWARD_DIR / f"{service_name}.log",
        SESSION_PORT_FORWARD_DIR / f"{service_name}.pid",
    )


def _read_pid(pid_path: Path) -> int | None:
    try:
        return int(pid_path.read_text().strip())
    except Exception:
        return None


def _pid_is_alive(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _terminate_pid(pid: int | None) -> None:
    if pid is None:
        return
    try:
        os.kill(pid, 15)
    except OSError:
        return
    deadline = time.time() + 5
    while time.time() < deadline:
        if not _pid_is_alive(pid):
            return
        time.sleep(0.2)
    try:
        os.kill(pid, 9)
    except OSError:
        return


def ensure_reusable_local_endpoint(
    namespace: str,
    service_name: str,
    local_url: str,
    probe_path: str,
) -> Dict[str, Any]:
    parsed = urlparse(local_url)
    host = (parsed.hostname or "").lower()
    port = parsed.port
    if host not in {"localhost", "127.0.0.1"} or port is None:
        return {"mode": "remote", "url": local_url}
    if endpoint_reachable(local_url, probe_path=probe_path):
        print_status(f"phase=port_forward: reusing session access for {service_name} at {local_url}")
        return {
            "mode": "reused",
            "url": local_url,
            "probe_path": probe_path,
            "state_dir": rel_path(SESSION_PORT_FORWARD_DIR),
        }

    SESSION_PORT_FORWARD_DIR.mkdir(parents=True, exist_ok=True)
    log_path, pid_path = _managed_port_forward_paths(service_name)
    pid = _read_pid(pid_path)
    if _pid_is_alive(pid):
        print_status(f"phase=port_forward: repairing stale session forward for {service_name} at {local_url}")
        _terminate_pid(pid)
        time.sleep(1)
    pid_path.unlink(missing_ok=True)

    cmd = ["kubectl", "port-forward", "-n", namespace, f"svc/{service_name}", f"{port}:{port}"]
    proc = start_process(cmd, ROOT, log_path)
    pid_path.write_text(f"{proc.pid}\n")

    deadline = time.time() + 20
    while time.time() < deadline:
        if proc.poll() is not None:
            break
        if endpoint_reachable(local_url, probe_path=probe_path, timeout_seconds=2):
            print_status(f"phase=port_forward: refreshed session access for {service_name} at {local_url}")
            return {
                "mode": "refreshed",
                "url": local_url,
                "probe_path": probe_path,
                "state_dir": rel_path(SESSION_PORT_FORWARD_DIR),
                "pid": proc.pid,
                "log": rel_path(log_path),
            }
        time.sleep(1)

    terminate_process(proc)
    pid_path.unlink(missing_ok=True)
    raise RuntimeError(
        f"local access for {service_name} at {local_url} is not reachable even after refreshing "
        f"the managed forward; see {rel_path(log_path)}"
    )


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


def prewarm_agent_runtime(agent_cfg: Dict[str, Any]) -> None:
    if not bool_value(agent_cfg.get("enabled"), False):
        return

    provider = str_value(agent_cfg.get("provider"), os.environ.get("LLM_PROVIDER", "")).strip().lower()
    if provider == "claude":
        provider = "anthropic"
    if provider != "ollama":
        return

    ensure_ollama_model_available()
    model = str_value(agent_cfg.get("model"), os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")).strip()
    if not model:
        raise RuntimeError("OLLAMA_MODEL must be set when warming Ollama")

    from agent_graph.reasoning.llm import ResponsesJSONClient

    print_status(f"phase=agent_prewarm: warming ollama model ({model})")
    client = ResponsesJSONClient(model=model, provider="ollama")
    client.complete_json(
        name="warmup",
        schema={
            "type": "object",
            "properties": {
                "ready": {"type": "boolean"},
            },
            "required": ["ready"],
            "additionalProperties": False,
        },
        prompt={
            "task": "Warm the local model runtime.",
            "instruction": "Return {'ready': true}.",
        },
    )
    print_status(f"phase=agent_prewarm: completed ({model})")


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


def validate_telemetry_sources(
    namespace: str,
    prom_url: str,
    jaeger_url: str,
    run_dir: Path,
    required_services: List[str],
) -> Dict[str, Any]:
    started = utc_now()
    cmd = [
        "python3",
        "./scripts/validate_telemetry.py",
        "--prom-url",
        prom_url,
        "--jaeger-url",
        jaeger_url,
        "--namespace",
        namespace,
        "--require-services",
        ",".join(required_services),
        "--wait-seconds",
        "45",
        "--poll-seconds",
        "5",
    ]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    log_path = run_dir / "telemetry_validation.log"
    log_path.write_text(
        "COMMAND: " + " ".join(shlex.quote(part) for part in cmd) + "\n\n"
        + "STDOUT:\n"
        + proc.stdout
        + "\nSTDERR:\n"
        + proc.stderr
    )
    payload: Dict[str, Any] = {}
    stdout = (proc.stdout or "").strip()
    if stdout:
        try:
            payload = json.loads(stdout)
        except Exception:
            payload = {}
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "started_at_utc": started,
        "finished_at_utc": utc_now(),
        "log": rel_path(log_path),
        "report": payload if isinstance(payload, dict) else {},
    }


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
        verify_chaos_mesh_health()
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

        print_status("phase=cleanup: removing lingering chaos resources")
        summary["steps"]["cleanup"] = cleanup_existing_chaos(namespace, run_dir / "cleanup.log")
        print_status("phase=cleanup: completed")

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
        if summary["steps"]["telemetry_validation"]["returncode"] != 0:
            raise RuntimeError("telemetry validation failed; see telemetry_validation.log")
        print_status("phase=telemetry: validated")

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
                summary["steps"]["agent"]["agent_variant"] = str_value(agent_report.get("agent_variant"), "pure_react")
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
        print(f"Experiment failed. Artifacts: {run_dir}", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
