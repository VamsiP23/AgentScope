from __future__ import annotations

import json
import shlex
from typing import Any, Dict, List

from agent_graph.tools.kubernetes_support import (
    aggregate_log_summaries,
    injector_event,
    summarize_deployment_pods,
    summarize_pod_logs,
    validate_kubectl_command,
)
from detectors.utils import run_cmd


class KubernetesTools:
    def __init__(self, kubectl_context: str = "") -> None:
        self.kubectl_context = kubectl_context.strip()

    def deployment_health(
        self,
        namespace: str,
        deployment: str,
        kubectl_context: str = "",
    ) -> Dict[str, Any]:
        result = run_cmd(self._kubectl_args(["get", "deployment", deployment, "-n", namespace, "-o", "json"], kubectl_context))
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

    def top_pod_restarts(
        self,
        namespace: str,
        limit: int = 5,
        kubectl_context: str = "",
    ) -> List[Dict[str, Any]]:
        result = run_cmd(self._kubectl_args(["get", "pods", "-n", namespace, "-o", "json"], kubectl_context))
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

    def recent_events(
        self,
        namespace: str,
        limit: int = 10,
        kubectl_context: str = "",
    ) -> List[Dict[str, Any]]:
        result = run_cmd(
            self._kubectl_args(
                ["get", "events", "-n", namespace, "--sort-by=.metadata.creationTimestamp", "-o", "json"],
                kubectl_context,
            )
        )
        if result["returncode"] != 0:
            return []

        items = json.loads(result["stdout"]).get("items", [])
        rows: List[Dict[str, Any]] = []
        for item in reversed(items):
            involved = item.get("involvedObject", {}) or {}
            kind = str(involved.get("kind", ""))
            name = str(involved.get("name", ""))
            api_version = str(involved.get("apiVersion", ""))
            reason = str(item.get("reason", ""))
            message = str(item.get("message", ""))

            if injector_event(api_version, kind, name, reason, message):
                continue

            rows.append(
                {
                    "reason": reason,
                    "message": message,
                    "type": item.get("type", ""),
                    "object": name,
                    "kind": kind,
                }
            )
            if len(rows) >= limit:
                break
        rows.reverse()
        return rows

    def deployment_pod_status(
        self,
        namespace: str,
        deployment: str,
        kubectl_context: str = "",
    ) -> Dict[str, Any]:
        dep_result = run_cmd(self._kubectl_args(["get", "deployment", deployment, "-n", namespace, "-o", "json"], kubectl_context))
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
        pods_result = run_cmd(
            self._kubectl_args(["get", "pods", "-n", namespace, "-l", selector_expr, "-o", "json"], kubectl_context)
        )
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
        return summarize_deployment_pods(dep, pod_items)

    def pods_for_service(
        self,
        namespace: str,
        service: str,
        kubectl_context: str = "",
    ) -> List[str]:
        pod_status = self.deployment_pod_status(namespace, service, kubectl_context)
        pods = [
            pod.get("name", "")
            for pod in pod_status.get("pods", []) or []
            if pod.get("name")
        ]
        if pods:
            return pods

        result = run_cmd(
            self._kubectl_args(["get", "pods", "-n", namespace, "-l", f"app={service}", "-o", "json"], kubectl_context)
        )
        if result["returncode"] != 0:
            return []
        try:
            payload = json.loads(result["stdout"])
        except Exception:
            return []
        return [
            item.get("metadata", {}).get("name", "")
            for item in payload.get("items", [])
            if item.get("metadata", {}).get("name")
        ]

    def service_logs(
        self,
        namespace: str,
        service: str,
        tail_lines: int = 100,
        kubectl_context: str = "",
    ) -> Dict[str, Any]:
        pods = self.pods_for_service(namespace, service, kubectl_context)
        if not pods:
            return {
                "service": service,
                "pod_name": "",
                "error_count": 0,
                "error_lines": [],
                "pods": [],
                "error": f"no pods found for service {service}",
            }

        pod_summaries: List[Dict[str, Any]] = []
        errors: List[str] = []

        for pod in pods:
            result = run_cmd(
                self._kubectl_args(["logs", pod, "-n", namespace, "--tail", str(max(1, tail_lines))], kubectl_context)
            )
            if result["returncode"] != 0:
                log_error = result["stderr"] or result["stdout"]
                errors.append(f"{pod}: {log_error}")
                pod_summaries.append(
                    {
                        "pod_name": pod,
                        "error_count": 1,
                        "error_lines": [log_error],
                        "signal_lines": [log_error],
                        "recent_lines": [log_error],
                        "log_error": log_error,
                    }
                )
                continue

            pod_summary = summarize_pod_logs(result["stdout"])
            pod_summary["pod_name"] = pod
            pod_summaries.append(pod_summary)

        return aggregate_log_summaries(service, pod_summaries, errors)

    def service_state(
        self,
        namespace: str,
        service: str,
        limit: int = 10,
        kubectl_context: str = "",
    ) -> Dict[str, Any]:
        deployment = self.deployment_health(namespace, service, kubectl_context)
        pod_status = self.deployment_pod_status(namespace, service, kubectl_context)
        recent_events = self.service_events(namespace, service, limit=limit, kubectl_context=kubectl_context)
        rollout_progressing = self.deployment_rollout_progressing(namespace, service, kubectl_context)

        pod_phases = [
            {
                "pod_name": pod.get("name", ""),
                "phase": pod.get("phase", ""),
                "ready": pod.get("ready", False),
                "restart_count": pod.get("restart_count", 0),
            }
            for pod in pod_status.get("pods", []) or []
        ]
        restart_count = sum(int(pod.get("restart_count", 0)) for pod in pod_status.get("pods", []) or [])

        error_message = deployment.get("raw_error") if not deployment.get("exists", False) else None
        return {
            "service": service,
            "desired_replicas": deployment.get("desired", 0),
            "available_replicas": deployment.get("available", 0),
            "pod_phases": pod_phases,
            "recent_events": recent_events,
            "rollout_progressing": rollout_progressing,
            "restart_count": restart_count,
            "error": error_message,
        }

    def service_events(
        self,
        namespace: str,
        service: str,
        limit: int = 10,
        kubectl_context: str = "",
    ) -> List[Dict[str, Any]]:
        result = run_cmd(
            self._kubectl_args(
                ["get", "events", "-n", namespace, "--sort-by=.metadata.creationTimestamp", "-o", "json"],
                kubectl_context,
            )
        )
        if result["returncode"] != 0:
            return []

        try:
            items = json.loads(result["stdout"]).get("items", [])
        except Exception:
            return []

        rows: List[Dict[str, Any]] = []
        service_lower = service.lower()
        for item in reversed(items):
            involved = item.get("involvedObject", {}) or {}
            kind = str(involved.get("kind", ""))
            name = str(involved.get("name", ""))
            api_version = str(involved.get("apiVersion", ""))
            reason = str(item.get("reason", ""))
            message = str(item.get("message", ""))

            if injector_event(api_version, kind, name, reason, message):
                continue

            haystack = f"{name} {message}".lower()
            if service_lower not in haystack:
                continue

            rows.append(
                {
                    "reason": reason,
                    "message": message,
                    "type": item.get("type", ""),
                    "object": name,
                    "kind": kind,
                }
            )
            if len(rows) >= limit:
                break
        rows.reverse()
        return rows

    def deployment_rollout_progressing(
        self,
        namespace: str,
        service: str,
        kubectl_context: str = "",
    ) -> bool:
        result = run_cmd(
            self._kubectl_args(["get", "deployment", service, "-n", namespace, "-o", "json"], kubectl_context)
        )
        if result["returncode"] != 0:
            return False

        try:
            dep = json.loads(result["stdout"])
        except Exception:
            return False

        desired = int(dep.get("spec", {}).get("replicas", 0))
        updated = int(dep.get("status", {}).get("updatedReplicas", 0))
        available = int(dep.get("status", {}).get("availableReplicas", 0))
        unavailable = int(dep.get("status", {}).get("unavailableReplicas", 0))
        conditions = dep.get("status", {}).get("conditions", []) or []
        progressing_condition = next((c for c in conditions if c.get("type") == "Progressing"), {})
        progressing_status = str(progressing_condition.get("status", "")) == "True"
        return progressing_status and (updated < desired or available < desired or unavailable > 0)

    def exec_shell(self, command: str, kubectl_context: str = "") -> Dict[str, Any]:
        try:
            tokens = shlex.split(command)
        except Exception as exc:
            return {
                "stdout": "",
                "stderr": "",
                "exit_code": 1,
                "rejected": True,
                "error": f"failed to parse command: {exc}",
            }

        allowed, reason = validate_kubectl_command(tokens)
        if not allowed:
            return {
                "stdout": "",
                "stderr": "",
                "exit_code": 1,
                "rejected": True,
                "error": reason,
            }

        result = run_cmd(self._inject_context(tokens, kubectl_context))
        return {
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "exit_code": result["returncode"],
            "rejected": False,
            "error": None,
        }

    def _kubectl_args(self, args: List[str], kubectl_context: str = "") -> List[str]:
        context = kubectl_context.strip() or self.kubectl_context
        base = ["kubectl"]
        if context:
            base.extend(["--context", context])
        base.extend(args)
        return base

    def _inject_context(self, tokens: List[str], kubectl_context: str = "") -> List[str]:
        context = kubectl_context.strip() or self.kubectl_context
        if not context or "--context" in tokens:
            return tokens
        return ["kubectl", "--context", context, *tokens[1:]]
