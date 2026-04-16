from __future__ import annotations

import json
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlencode
from urllib.request import urlopen

from runner_common import (
    CORE_DEPLOYMENTS,
    ROOT,
    epoch_to_utc,
    rel_path,
    run_cmd,
    utc_now,
)


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


def prom_vector_map(prom_url: str, query: str, *, key: str, eval_time: float) -> Dict[str, float]:
    data = prom_query(prom_url, query, eval_time=eval_time)
    parsed: Dict[str, float] = {}
    for row in data.get("result", []):
        item_key = row.get("metric", {}).get(key)
        if not item_key:
            continue
        try:
            parsed[item_key] = float(row.get("value", [0, "0"])[1])
        except (TypeError, ValueError):
            parsed[item_key] = 0.0
    return parsed


def prometheus_service_metrics(prom_url: str, window_seconds: int, eval_time: float) -> Dict[str, Dict[str, Any]]:
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
    for latency_query in [
        f"histogram_quantile(0.99, sum(increase(duration_milliseconds_bucket[{window}])) by (service_name, le))",
        f"histogram_quantile(0.99, sum(increase(duration_bucket[{window}])) by (service_name, le))",
        f"histogram_quantile(0.99, sum(increase(latency_bucket[{window}])) by (service_name, le))",
    ]:
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

    result: Dict[str, Dict[str, Any]] = {}
    services = sorted(set(request_totals) | set(error_totals) | set(p99_latency))
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
    if proc.returncode == 0:
        return [line.strip() for line in proc.stdout.splitlines() if line.strip()]

    stderr = (proc.stderr or "").lower()
    stdout = (proc.stdout or "").lower()
    if "the server doesn't have a resource type" in stderr or "notfound" in stderr:
        return []
    if "the server doesn't have a resource type" in stdout or "notfound" in stdout:
        return []
    raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "kubectl command failed")


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

    return {"services": services, "deployments": deployments}


def collect_window_metrics(namespace: str, prom_url: str, start_epoch: float, end_epoch: float) -> Dict[str, Any]:
    window_seconds = max(1, int(end_epoch - start_epoch))
    prom = prometheus_service_metrics(prom_url, window_seconds, end_epoch)
    k8s = kubernetes_snapshot_metrics(namespace)
    services = sorted(set(prom["services"]) | set(k8s["services"]) | set(k8s["deployments"]))

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
    required = ["frontend", "prometheus", "jaeger", "opentelemetrycollector", "kube-state-metrics"]
    deployments_payload = kubectl_json(["kubectl", "get", "deploy", "-n", namespace, "-o", "json"])
    available = {
        item.get("metadata", {}).get("name"): int(item.get("status", {}).get("availableReplicas", 0) or 0)
        for item in deployments_payload.get("items", [])
    }
    missing = [name for name in required if available.get(name, 0) < 1]
    if missing:
        raise RuntimeError(f"required deployments unavailable in namespace {namespace}: {', '.join(missing)}")


def list_existing_native_fault_state(namespace: str) -> List[str]:
    existing: List[str] = []
    existing.extend(
        kubectl_lines_or_empty(
            [
                "kubectl",
                "get",
                "configmap",
                "-n",
                namespace,
                "-l",
                "agentscope.dev/native-fault=true",
                "-o",
                "name",
            ]
        )
    )
    existing.extend(
        kubectl_lines_or_empty(
            [
                "kubectl",
                "get",
                "job",
                "-n",
                namespace,
                "-l",
                "agentscope.dev/native-fault=true",
                "-o",
                "name",
            ]
        )
    )
    existing.extend(
        kubectl_lines_or_empty(
            [
                "kubectl",
                "get",
                "pod",
                "-n",
                namespace,
                "-l",
                "agentscope.dev/native-fault=true",
                "-o",
                "name",
            ]
        )
    )
    return existing


def cleanup_existing_native_faults(namespace: str, log_path: Path) -> Dict[str, Any]:
    existing = list_existing_native_fault_state(namespace)
    log_lines = [f"timestamp_utc: {utc_now()}", f"namespace: {namespace}", f"found: {len(existing)}"]
    if existing:
        log_lines.append("existing_objects:")
        log_lines.extend(f"  - {name}" for name in existing)
    else:
        log_lines.append("existing_objects: []")

    deleted: List[str] = []
    for resource in ["job", "pod", "configmap"]:
        names = kubectl_lines_or_empty(
            [
                "kubectl",
                "get",
                resource,
                "-n",
                namespace,
                "-l",
                "agentscope.dev/native-fault=true",
                "-o",
                "name",
            ]
        )
        if not names:
            continue
        proc = kubectl_run(
            [
                "kubectl",
                "delete",
                resource,
                "-n",
                namespace,
                "-l",
                "agentscope.dev/native-fault=true",
                "--ignore-not-found",
                "--timeout=120s",
            ]
        )
        log_lines.extend(
            [
                "",
                "COMMAND: " + " ".join(shlex.quote(part) for part in proc.args),
                "STDOUT:",
                proc.stdout.rstrip(),
                "STDERR:",
                proc.stderr.rstrip(),
            ]
        )
        if proc.returncode != 0:
            log_path.write_text("\n".join(log_lines) + "\n")
            raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"failed to delete native {resource}")
        deleted.extend(names)

    deadline = time.time() + 60
    while deleted and time.time() < deadline:
        remaining = list_existing_native_fault_state(namespace)
        if not remaining:
            break
        time.sleep(2)

    remaining = list_existing_native_fault_state(namespace)
    log_lines.extend(["", f"deleted: {len(deleted)}"])
    if deleted:
        log_lines.extend(f"  - {name}" for name in deleted)
    else:
        log_lines.append("deleted_objects: []")
    log_lines.append(f"remaining: {len(remaining)}")
    if remaining:
        log_lines.extend(f"  - {name}" for name in remaining)
    log_path.write_text("\n".join(log_lines) + "\n")

    if remaining:
        raise RuntimeError(f"stale native fault resources still present in namespace {namespace}: {', '.join(remaining)}")

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
            unhealthy.append({"deployment": name, "desired": desired, "available": available, "ready": ready})
    return unhealthy


def assess_reset_need(namespace: str) -> Dict[str, Any]:
    reasons: List[str] = []
    details: Dict[str, Any] = {}

    try:
        stale_native = list_existing_native_fault_state(namespace)
    except Exception as exc:
        stale_native = []
        reasons.append(f"failed to inspect native fault resources: {exc}")
    if stale_native:
        reasons.append(f"found {len(stale_native)} lingering native fault resources")
        details["stale_native_fault_resources"] = stale_native

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

    return {"needs_reset": bool(reasons), "reasons": reasons, "details": details, "checked_at_utc": utc_now()}


def capture_snapshot(namespace: str, label: str, out_dir: Path) -> Dict[str, Any]:
    snapshots = {}
    commands = {
        f"{label}_deployments.txt": ["kubectl", "get", "deploy", "-n", namespace],
        f"{label}_pods.txt": ["kubectl", "get", "pods", "-n", namespace],
        f"{label}_services.txt": ["kubectl", "get", "services", "-n", namespace, "-o", "wide"],
        f"{label}_endpoints.txt": ["kubectl", "get", "endpoints", "-n", namespace, "-o", "wide"],
        f"{label}_endpointslices.txt": ["kubectl", "get", "endpointslices", "-n", namespace, "-o", "wide"],
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
