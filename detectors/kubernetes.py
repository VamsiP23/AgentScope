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
        ready = int(dep.get("status", {}).get("readyReplicas", 0) or 0)
        updated = int(dep.get("status", {}).get("updatedReplicas", 0) or 0)
        unavailable = int(dep.get("status", {}).get("unavailableReplicas", 0) or 0)
        observed_generation = int(dep.get("status", {}).get("observedGeneration", 0) or 0)
        generation = int(dep.get("metadata", {}).get("generation", 0) or 0)
        conditions = dep.get("status", {}).get("conditions", []) or []
        progressing = next((item for item in conditions if item.get("type") == "Progressing"), {})
        rollout_observed = observed_generation >= generation
        rollout_updated = desired == 0 or updated >= desired
        return {
            "exists": True,
            "desired": desired,
            "available": available,
            "ready": ready,
            "updated": updated,
            "unavailable": unavailable,
            "generation": generation,
            "observed_generation": observed_generation,
            "rollout_observed": rollout_observed,
            "rollout_updated": rollout_updated,
            "progressing_reason": progressing.get("reason", ""),
            "progressing_message": progressing.get("message", ""),
            "healthy": available >= max(1, desired) and unavailable == 0 and rollout_observed and rollout_updated,
        }

    def service_endpoint_health(self, namespace: str, service: str) -> Dict[str, Any]:
        result = run_cmd(["kubectl", "get", "endpoints", service, "-n", namespace, "-o", "json"])
        if result["returncode"] != 0:
            return {
                "exists": False,
                "ready_addresses": 0,
                "not_ready_addresses": 0,
                "healthy": False,
                "raw_error": result["stderr"] or result["stdout"],
            }
        endpoints = json.loads(result["stdout"])
        ready = 0
        not_ready = 0
        ports = []
        for subset in endpoints.get("subsets", []) or []:
            ready += len(subset.get("addresses", []) or [])
            not_ready += len(subset.get("notReadyAddresses", []) or [])
            ports.extend(port.get("port") for port in subset.get("ports", []) or [] if port.get("port") is not None)
        return {
            "exists": True,
            "ready_addresses": ready,
            "not_ready_addresses": not_ready,
            "ports": ports,
            "healthy": ready > 0,
        }

    def service_port_alignment(self, namespace: str, service: str) -> Dict[str, Any]:
        svc_result = run_cmd(["kubectl", "get", "service", service, "-n", namespace, "-o", "json"])
        if svc_result["returncode"] != 0:
            return {
                "exists": False,
                "aligned": False,
                "raw_error": svc_result["stderr"] or svc_result["stdout"],
            }
        svc = json.loads(svc_result["stdout"])
        selector = svc.get("spec", {}).get("selector", {}) or {}
        ports = svc.get("spec", {}).get("ports", []) or []
        if not selector:
            return {
                "exists": True,
                "aligned": False,
                "selector": selector,
                "service_ports": ports,
                "reason": "service has no selector",
            }

        selector_arg = ",".join(f"{key}={value}" for key, value in sorted(selector.items()))
        pod_result = run_cmd(["kubectl", "get", "pods", "-n", namespace, "-l", selector_arg, "-o", "json"])
        if pod_result["returncode"] != 0:
            return {
                "exists": True,
                "aligned": False,
                "selector": selector,
                "service_ports": ports,
                "raw_error": pod_result["stderr"] or pod_result["stdout"],
            }

        pods = json.loads(pod_result["stdout"]).get("items", []) or []
        if not pods:
            return {
                "exists": True,
                "aligned": True,
                "selector": selector,
                "service_ports": ports,
                "container_ports": [],
                "named_ports": {},
                "mismatches": [],
                "reason": "service selector currently matches no pods",
            }

        container_ports = set()
        named_ports: Dict[str, int] = {}
        for pod in pods:
            for container in pod.get("spec", {}).get("containers", []) or []:
                for port in container.get("ports", []) or []:
                    number = port.get("containerPort")
                    if number is not None:
                        container_ports.add(int(number))
                    name = port.get("name")
                    if name and number is not None:
                        named_ports[str(name)] = int(number)

        mismatches = []
        for port in ports:
            target = port.get("targetPort", port.get("port"))
            if isinstance(target, str):
                resolved = named_ports.get(target)
            else:
                resolved = int(target) if target is not None else None
            if resolved is None or resolved not in container_ports:
                mismatches.append(
                    {
                        "service_port": port.get("port"),
                        "target_port": target,
                        "resolved_target_port": resolved,
                    }
                )

        return {
            "exists": True,
            "aligned": not mismatches,
            "selector": selector,
            "service_ports": ports,
            "container_ports": sorted(container_ports),
            "named_ports": named_ports,
            "mismatches": mismatches,
        }

    def active_native_stress_jobs(self, namespace: str) -> List[Dict[str, Any]]:
        result = run_cmd(
            [
                "kubectl",
                "get",
                "pods",
                "-n",
                namespace,
                "-l",
                "agentscope.dev/fault-type=stress-job",
                "-o",
                "json",
            ]
        )
        if result["returncode"] != 0:
            return []
        pods = json.loads(result["stdout"]).get("items", []) or []
        rows: List[Dict[str, Any]] = []
        for pod in pods:
            phase = pod.get("status", {}).get("phase", "Unknown")
            if phase not in {"Pending", "Running"}:
                continue
            rows.append(
                {
                    "pod": pod.get("metadata", {}).get("name", ""),
                    "phase": phase,
                    "node": pod.get("spec", {}).get("nodeName", ""),
                    "job": (pod.get("metadata", {}).get("labels", {}) or {}).get("job-name", ""),
                }
            )
        return rows

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
