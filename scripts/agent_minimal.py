#!/usr/bin/env python3
"""Minimal agent workflow for incident detection and safe remediation.

Workflow:
1) Detect: read Prometheus error/traffic metrics + deployment health.
2) Diagnose: gather top error services and pod restart hints.
3) Act: run an allowlisted action (rollout restart on target deployment).
4) Verify: wait for deployment health and lower error ratio.

Outputs a JSON report in agent_runs/<timestamp>/incident_report.json.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode
from urllib.request import urlopen


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ts_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_cmd(cmd: List[str]) -> Dict[str, Any]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "cmd": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def require_kubectl() -> None:
    if shutil.which("kubectl") is None:
        print("kubectl is required but not found in PATH.", file=sys.stderr)
        sys.exit(1)


def prom_query(prom_url: str, query: str) -> Dict[str, Any]:
    params = urlencode({"query": query})
    url = f"{prom_url.rstrip('/')}/api/v1/query?{params}"
    with urlopen(url, timeout=10) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus query failed: {payload}")
    return payload.get("data", {})


def instant_scalar(prom_url: str, query: str) -> float:
    data = prom_query(prom_url, query)
    results = data.get("result", [])
    if not results:
        return 0.0
    value = results[0].get("value", [0, "0"])[1]
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def vector_query(prom_url: str, query: str) -> List[Dict[str, Any]]:
    data = prom_query(prom_url, query)
    return data.get("result", [])


def deployment_health(namespace: str, deployment: str) -> Dict[str, Any]:
    result = run_cmd(
        [
            "kubectl",
            "get",
            "deployment",
            deployment,
            "-n",
            namespace,
            "-o",
            "json",
        ]
    )
    if result["returncode"] != 0:
        return {
            "exists": False,
            "desired": 0,
            "available": 0,
            "healthy": False,
            "raw_error": result["stderr"] or result["stdout"],
        }
    dep = json.loads(result["stdout"])
    desired = int(dep.get("spec", {}).get("replicas", 0))
    available = int(dep.get("status", {}).get("availableReplicas", 0))
    return {
        "exists": True,
        "desired": desired,
        "available": available,
        "healthy": available >= max(1, desired),
    }


def top_pod_restarts(namespace: str, limit: int = 5) -> List[Dict[str, Any]]:
    result = run_cmd(["kubectl", "get", "pods", "-n", namespace, "-o", "json"])
    if result["returncode"] != 0:
        return []
    pods = json.loads(result["stdout"]).get("items", [])
    rows: List[Dict[str, Any]] = []
    for pod in pods:
        pod_name = pod.get("metadata", {}).get("name", "")
        for c in pod.get("status", {}).get("containerStatuses", []) or []:
            restarts = int(c.get("restartCount", 0))
            if restarts > 0:
                rows.append(
                    {
                        "pod": pod_name,
                        "container": c.get("name", ""),
                        "restart_count": restarts,
                    }
                )
    rows.sort(key=lambda r: r["restart_count"], reverse=True)
    return rows[:limit]


@dataclass
class Detection:
    timestamp_utc: str
    total_rps: float
    error_rps: float
    error_ratio: float
    deployment_healthy: bool
    triggered: bool
    reason: str


def detect_incident(
    prom_url: str,
    namespace: str,
    target: str,
    window: str,
    error_ratio_threshold: float,
    min_total_rps: float,
) -> Detection:
    total_rps = instant_scalar(prom_url, f"sum(rate(calls_total[{window}]))")
    error_rps = instant_scalar(
        prom_url,
        f'sum(rate(calls_total{{status_code="STATUS_CODE_ERROR"}}[{window}]))',
    )
    ratio = (error_rps / total_rps) if total_rps > 0 else 0.0
    dep = deployment_health(namespace, target)
    dep_healthy = dep.get("healthy", False)

    high_error = total_rps >= min_total_rps and ratio >= error_ratio_threshold
    dep_down = not dep_healthy

    triggered = high_error or dep_down
    reason_parts = []
    if high_error:
        reason_parts.append(
            f"high_error_ratio={ratio:.3f} (threshold={error_ratio_threshold:.3f})"
        )
    if dep_down:
        reason_parts.append(
            f"deployment_unhealthy available={dep.get('available', 0)}/desired={dep.get('desired', 0)}"
        )
    if not reason_parts:
        reason_parts.append("no_trigger")

    return Detection(
        timestamp_utc=utc_now(),
        total_rps=total_rps,
        error_rps=error_rps,
        error_ratio=ratio,
        deployment_healthy=dep_healthy,
        triggered=triggered,
        reason="; ".join(reason_parts),
    )


def diagnose(
    prom_url: str, namespace: str, window: str, target: str
) -> Dict[str, Any]:
    top_errors = vector_query(
        prom_url,
        f'sum(rate(calls_total{{status_code="STATUS_CODE_ERROR"}}[{window}])) by (service_name)',
    )
    top_errors_sorted: List[Dict[str, Any]] = []
    for row in top_errors:
        service = row.get("metric", {}).get("service_name", "unknown")
        value = float(row.get("value", [0, "0"])[1])
        top_errors_sorted.append({"service_name": service, "error_rps": value})
    top_errors_sorted.sort(key=lambda r: r["error_rps"], reverse=True)
    top_errors_sorted = top_errors_sorted[:5]

    restarts = top_pod_restarts(namespace, limit=5)
    dep = deployment_health(namespace, target)

    hypothesis = []
    if not dep.get("healthy", False):
        hypothesis.append(f"{target} deployment is not healthy.")
    if top_errors_sorted:
        hypothesis.append(
            f"Top error service: {top_errors_sorted[0]['service_name']} ({top_errors_sorted[0]['error_rps']:.3f} rps)."
        )
    if restarts:
        hypothesis.append(
            f"Highest restart pod: {restarts[0]['pod']} ({restarts[0]['restart_count']} restarts)."
        )
    if not hypothesis:
        hypothesis.append("No strong root-cause signal found.")

    return {
        "timestamp_utc": utc_now(),
        "target_deployment_health": dep,
        "top_error_services": top_errors_sorted,
        "top_pod_restarts": restarts,
        "hypothesis": " ".join(hypothesis),
    }


def act(namespace: str, target: str, dry_run: bool) -> Dict[str, Any]:
    action = f"kubectl rollout restart deployment/{target} -n {namespace}"
    if dry_run:
        return {
            "timestamp_utc": utc_now(),
            "action": action,
            "executed": False,
            "result": "dry_run",
        }

    restart = run_cmd(
        [
            "kubectl",
            "rollout",
            "restart",
            f"deployment/{target}",
            "-n",
            namespace,
        ]
    )
    status = run_cmd(
        [
            "kubectl",
            "rollout",
            "status",
            f"deployment/{target}",
            "-n",
            namespace,
            "--timeout=240s",
        ]
    )
    return {
        "timestamp_utc": utc_now(),
        "action": action,
        "executed": True,
        "restart_result": restart,
        "rollout_status_result": status,
    }


def verify(
    prom_url: str,
    namespace: str,
    target: str,
    window: str,
    error_ratio_threshold: float,
    min_total_rps: float,
    wait_seconds: int,
    timeout_seconds: int,
) -> Dict[str, Any]:
    time.sleep(wait_seconds)
    deadline = time.time() + timeout_seconds
    history: List[Dict[str, Any]] = []
    while time.time() < deadline:
        d = detect_incident(
            prom_url,
            namespace,
            target,
            window,
            error_ratio_threshold,
            min_total_rps,
        )
        row = asdict(d)
        history.append(row)
        if not d.triggered:
            return {
                "timestamp_utc": utc_now(),
                "recovered": True,
                "history": history,
            }
        time.sleep(15)
    return {
        "timestamp_utc": utc_now(),
        "recovered": False,
        "history": history,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Minimal agent workflow (detect -> diagnose -> act -> verify)."
    )
    p.add_argument("--namespace", default="default")
    p.add_argument("--prom-url", default="http://localhost:9090")
    p.add_argument("--target-deployment", default="cartservice")
    p.add_argument("--window", default="2m", help="PromQL rate window, e.g. 2m")
    p.add_argument("--error-ratio-threshold", type=float, default=0.10)
    p.add_argument("--min-total-rps", type=float, default=0.10)
    p.add_argument("--verify-wait-seconds", type=int, default=45)
    p.add_argument("--verify-timeout-seconds", type=int, default=180)
    p.add_argument("--out-dir", default="agent_runs")
    p.add_argument("--dry-run", action="store_true")
    return p


def main() -> int:
    args = build_parser().parse_args()
    require_kubectl()

    run_id = ts_compact()
    run_dir = Path(args.out_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    report_path = run_dir / "incident_report.json"

    report: Dict[str, Any] = {
        "run_id": run_id,
        "started_at_utc": utc_now(),
        "config": vars(args),
    }

    try:
        detection = detect_incident(
            args.prom_url,
            args.namespace,
            args.target_deployment,
            args.window,
            args.error_ratio_threshold,
            args.min_total_rps,
        )
        report["detection"] = asdict(detection)

        if not detection.triggered:
            report["result"] = "no_incident_detected"
            report["finished_at_utc"] = utc_now()
            report_path.write_text(json.dumps(report, indent=2))
            print(f"No incident detected. Report: {report_path}")
            return 0

        diagnosis = diagnose(
            args.prom_url,
            args.namespace,
            args.window,
            args.target_deployment,
        )
        report["diagnosis"] = diagnosis

        action = act(args.namespace, args.target_deployment, args.dry_run)
        report["action"] = action

        if args.dry_run:
            report["result"] = "incident_detected_dry_run"
            report["finished_at_utc"] = utc_now()
            report_path.write_text(json.dumps(report, indent=2))
            print(f"Incident detected (dry run). Report: {report_path}")
            return 0

        verification = verify(
            args.prom_url,
            args.namespace,
            args.target_deployment,
            args.window,
            args.error_ratio_threshold,
            args.min_total_rps,
            args.verify_wait_seconds,
            args.verify_timeout_seconds,
        )
        report["verification"] = verification
        report["result"] = "recovered" if verification["recovered"] else "not_recovered"
        report["finished_at_utc"] = utc_now()
        report_path.write_text(json.dumps(report, indent=2))
        print(f"Run complete: {report['result']}. Report: {report_path}")
        return 0 if verification["recovered"] else 2

    except Exception as exc:  # pylint: disable=broad-except
        report["result"] = "error"
        report["error"] = str(exc)
        report["finished_at_utc"] = utc_now()
        report_path.write_text(json.dumps(report, indent=2))
        print(f"Agent run failed. Report: {report_path}", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
