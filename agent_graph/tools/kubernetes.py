from __future__ import annotations

import json
from typing import Any, Dict, List

from detectors.kubernetes import KubernetesClient as DetectorKubernetesClient
from detectors.utils import run_cmd


class KubernetesTools:
    def __init__(self) -> None:
        self.client = DetectorKubernetesClient()

    def deployment_health(self, namespace: str, deployment: str) -> Dict[str, Any]:
        return self.client.deployment_health(namespace, deployment)

    def top_pod_restarts(self, namespace: str, limit: int = 5) -> List[Dict[str, Any]]:
        return self.client.top_pod_restarts(namespace, limit=limit)

    def recent_events(self, namespace: str, limit: int = 10) -> List[Dict[str, Any]]:
        result = run_cmd([
            "kubectl",
            "get",
            "events",
            "-n",
            namespace,
            "--sort-by=.metadata.creationTimestamp",
            "-o",
            "json",
        ])
        if result["returncode"] != 0:
            return []
        items = json.loads(result["stdout"]).get("items", [])
        tail = items[-limit:]
        rows: List[Dict[str, Any]] = []
        for item in tail:
            rows.append(
                {
                    "reason": item.get("reason", ""),
                    "message": item.get("message", ""),
                    "type": item.get("type", ""),
                    "object": item.get("involvedObject", {}).get("name", ""),
                }
            )
        return rows

    def deployment_pod_status(self, namespace: str, deployment: str) -> Dict[str, Any]:
        dep_result = run_cmd(["kubectl", "get", "deployment", deployment, "-n", namespace, "-o", "json"])
        if dep_result["returncode"] != 0:
            return {
                "exists": False,
                "selector": {},
                "pods": [],
                "pod_count": 0,
                "ready_pod_count": 0,
                "progressing": False,
            }

        dep = json.loads(dep_result["stdout"])
        selector = dep.get("spec", {}).get("selector", {}).get("matchLabels", {}) or {}
        if not selector:
            return {
                "exists": True,
                "selector": {},
                "pods": [],
                "pod_count": 0,
                "ready_pod_count": 0,
                "progressing": False,
            }

        selector_expr = ",".join(f"{key}={value}" for key, value in selector.items())
        pods_result = run_cmd([
            "kubectl",
            "get",
            "pods",
            "-n",
            namespace,
            "-l",
            selector_expr,
            "-o",
            "json",
        ])
        if pods_result["returncode"] != 0:
            return {
                "exists": True,
                "selector": selector,
                "pods": [],
                "pod_count": 0,
                "ready_pod_count": 0,
                "progressing": False,
            }

        pod_items = json.loads(pods_result["stdout"]).get("items", [])
        pods: List[Dict[str, Any]] = []
        ready_pod_count = 0
        for item in pod_items:
            conditions = item.get("status", {}).get("conditions", []) or []
            ready = any(
                condition.get("type") == "Ready" and condition.get("status") == "True"
                for condition in conditions
            )
            if ready:
                ready_pod_count += 1
            pods.append(
                {
                    "name": item.get("metadata", {}).get("name", ""),
                    "phase": item.get("status", {}).get("phase", ""),
                    "ready": ready,
                }
            )

        return {
            "exists": True,
            "selector": selector,
            "pods": pods,
            "pod_count": len(pods),
            "ready_pod_count": ready_pod_count,
            "progressing": len(pods) > 0 and ready_pod_count < len(pods),
        }
