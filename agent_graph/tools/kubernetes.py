from __future__ import annotations

import json
import re
import shlex
from typing import Any, Dict, List, Optional

from detectors.utils import run_cmd


ERROR_LINE_PATTERN = re.compile(
    r"(?i)(error|exception|fatal|panic|traceback|timeout|deadline exceeded|connection refused|crashloop|unavailable)"
)
SIGNAL_LINE_PATTERN = re.compile(
    r"(?i)(error|exception|fatal|panic|traceback|timeout|deadline exceeded|connection refused|unavailable|warn|throttl|oom|killed|refused|failed)"
)
MAX_LOG_LINES_RETURNED = 8
FORBIDDEN_SHELL_TOKENS = {"|", "||", "&", "&&", ";", ">", ">>", "<", "<<", "$(", "`"}
ALLOWED_KUBECTL_VERBS = {"get", "describe", "logs", "rollout", "delete", "patch"}
RESOURCE_LIMIT_KEYS = {"limits", "requests"}


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

            if self._is_injector_event(api_version, kind, name, reason, message):
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
        pods: List[Dict[str, Any]] = []
        ready_pod_count = 0
        for item in pod_items:
            conditions = item.get("status", {}).get("conditions", []) or []
            ready = any(
                condition.get("type") == "Ready" and condition.get("status") == "True"
                for condition in conditions
            )
            restart_count = sum(
                int(status.get("restartCount", 0))
                for status in item.get("status", {}).get("containerStatuses", []) or []
            )
            if ready:
                ready_pod_count += 1
            pods.append(
                {
                    "name": item.get("metadata", {}).get("name", ""),
                    "phase": item.get("status", {}).get("phase", ""),
                    "ready": ready,
                    "restart_count": restart_count,
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
        aggregate_error_lines: List[str] = []
        aggregate_signal_lines: List[str] = []
        aggregate_recent_lines: List[str] = []
        errors: List[str] = []

        for pod in pods:
            result = run_cmd(
                self._kubectl_args(["logs", pod, "-n", namespace, "--tail", str(max(1, tail_lines))], kubectl_context)
            )
            if result["returncode"] != 0:
                log_error = result["stderr"] or result["stdout"]
                errors.append(f"{pod}: {log_error}")
                aggregate_error_lines.append(log_error)
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

            all_lines = [line.strip() for line in result["stdout"].splitlines() if line.strip()]
            error_lines = [line for line in all_lines if ERROR_LINE_PATTERN.search(line)]
            signal_lines = [line for line in all_lines if SIGNAL_LINE_PATTERN.search(line)]
            recent_lines = all_lines[-MAX_LOG_LINES_RETURNED:]
            aggregate_error_lines.extend(error_lines)
            aggregate_signal_lines.extend(signal_lines[:MAX_LOG_LINES_RETURNED])
            aggregate_recent_lines.extend(recent_lines)
            pod_summaries.append(
                {
                    "pod_name": pod,
                    "error_count": len(error_lines),
                    "error_lines": error_lines[:MAX_LOG_LINES_RETURNED],
                    "signal_lines": signal_lines[:MAX_LOG_LINES_RETURNED],
                    "recent_lines": recent_lines,
                }
            )

        pod_summaries.sort(key=lambda item: item.get("error_count", 0), reverse=True)
        primary = pod_summaries[0] if pod_summaries else {
            "pod_name": "",
            "error_count": 0,
            "error_lines": [],
            "signal_lines": [],
            "recent_lines": [],
        }

        return {
            "service": service,
            "pod_name": primary.get("pod_name", ""),
            "error_count": sum(item.get("error_count", 0) for item in pod_summaries),
            "error_lines": aggregate_error_lines[:MAX_LOG_LINES_RETURNED],
            "signal_lines": aggregate_signal_lines[:MAX_LOG_LINES_RETURNED],
            "recent_lines": primary.get("recent_lines", [])[:MAX_LOG_LINES_RETURNED],
            "pods": pod_summaries,
            "error": "; ".join(errors) if errors else None,
        }

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

            if self._is_injector_event(api_version, kind, name, reason, message):
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

        allowed, reason = self._validate_kubectl_command(tokens)
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

    def _is_injector_event(self, api_version: str, kind: str, name: str, reason: str, message: str) -> bool:
        if "chaos-mesh.org" in api_version:
            return True
        if kind.lower().endswith("chaos"):
            return True
        if name.endswith("-pod-kill") or ("-to-" in name and ("delay" in name or "loss" in name)):
            return True
        if reason in {"Started", "Applied", "Recovered", "FinalizerInited", "Updated", "TimeUp"} and (
            "chaos" in message.lower() or "chaos" in name.lower()
        ):
            return True
        return False

    def _validate_kubectl_command(self, tokens: List[str]) -> tuple[bool, str]:
        if not tokens:
            return False, "empty command"
        if any(token in FORBIDDEN_SHELL_TOKENS for token in tokens):
            return False, "shell operators are not allowed"
        if tokens[0] != "kubectl":
            return False, "only kubectl commands are allowed"

        verb_index = self._find_kubectl_verb_index(tokens)
        if verb_index is None:
            return False, "no supported kubectl verb found"

        verb = tokens[verb_index]
        if verb not in ALLOWED_KUBECTL_VERBS:
            return False, f"kubectl {verb} is not whitelisted"

        if verb in {"get", "describe", "logs"}:
            return True, ""

        if verb == "rollout":
            subcommand_index = self._first_non_flag_index(tokens, verb_index + 1)
            if subcommand_index is None:
                return False, "kubectl rollout requires a subcommand"
            subcommand = tokens[subcommand_index]
            if subcommand not in {"undo", "restart"}:
                return False, "only kubectl rollout undo/restart are allowed"
            return True, ""

        if verb == "delete":
            resource_index = self._first_non_flag_index(tokens, verb_index + 1)
            if resource_index is None:
                return False, "kubectl delete requires a resource"
            resource = tokens[resource_index]
            if resource != "pod" and not resource.startswith("pod/"):
                return False, "only kubectl delete pod is allowed"
            return True, ""

        if verb == "patch":
            return self._validate_patch_command(tokens[verb_index:])

        return False, "unsupported kubectl command"

    def _find_kubectl_verb_index(self, tokens: List[str]) -> Optional[int]:
        for index, token in enumerate(tokens[1:], start=1):
            if token in ALLOWED_KUBECTL_VERBS:
                return index
        return None

    def _first_non_flag_index(self, tokens: List[str], start: int) -> Optional[int]:
        for index in range(start, len(tokens)):
            if not tokens[index].startswith("-"):
                return index
        return None

    def _validate_patch_command(self, patch_tokens: List[str]) -> tuple[bool, str]:
        if len(patch_tokens) < 3:
            return False, "kubectl patch requires a resource target"
        patch_arg: Optional[str] = None
        for index, token in enumerate(patch_tokens):
            if token in {"-p", "--patch"}:
                if index + 1 >= len(patch_tokens):
                    return False, "kubectl patch requires a patch payload"
                patch_arg = patch_tokens[index + 1]
                break
        if patch_arg is None:
            return False, "kubectl patch is only allowed with inline JSON patch payload"
        try:
            payload = json.loads(patch_arg)
        except Exception as exc:
            return False, f"patch payload must be valid JSON: {exc}"
        if not self._patch_only_touches_resources(payload):
            return False, "kubectl patch is restricted to container resource requests/limits"
        return True, ""

    def _patch_only_touches_resources(self, payload: Any) -> bool:
        if not isinstance(payload, dict):
            return False
        if "spec" not in payload:
            return False
        spec = payload.get("spec")
        if not isinstance(spec, dict):
            return False

        if "template" in spec:
            pod_spec = (((spec.get("template") or {}).get("spec")) if isinstance(spec.get("template"), dict) else None)
        else:
            pod_spec = spec

        if not isinstance(pod_spec, dict):
            return False

        allowed_top_level = {"containers", "initContainers"}
        if any(key not in allowed_top_level for key in pod_spec.keys()):
            return False

        for container_key in ("containers", "initContainers"):
            containers = pod_spec.get(container_key)
            if containers is None:
                continue
            if not isinstance(containers, list):
                return False
            for container in containers:
                if not isinstance(container, dict):
                    return False
                for key in container.keys():
                    if key not in {"name", "resources"}:
                        return False
                resources = container.get("resources")
                if not isinstance(resources, dict):
                    return False
                if any(key not in RESOURCE_LIMIT_KEYS for key in resources.keys()):
                    return False
        return True
