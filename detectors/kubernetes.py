from __future__ import annotations

import json
from typing import Any, Dict, List

from detectors.utils import run_cmd


class KubernetesClient:
    def deployment_health(self, namespace: str, deployment: str) -> Dict[str, Any]:
        result = run_cmd(["kubectl", "get", "deployment", deployment, "-n", namespace, "-o", "json"])
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

    def top_pod_restarts(self, namespace: str, limit: int = 10) -> List[Dict[str, Any]]:
        result = run_cmd(["kubectl", "get", "pods", "-n", namespace, "-o", "json"])
        if result["returncode"] != 0:
            return []
        pods = json.loads(result["stdout"]).get("items", [])
        rows: List[Dict[str, Any]] = []
        for pod in pods:
            pod_name = pod.get("metadata", {}).get("name", "")
            for status in pod.get("status", {}).get("containerStatuses", []) or []:
                count = int(status.get("restartCount", 0))
                if count > 0:
                    rows.append(
                        {
                            "pod": pod_name,
                            "container": status.get("name", ""),
                            "restart_count": count,
                        }
                    )
        rows.sort(key=lambda item: item["restart_count"], reverse=True)
        return rows[:limit]
