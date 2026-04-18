from __future__ import annotations

import json
import re
from typing import Any, Dict, List


ERROR_LINE_PATTERN = re.compile(
    r"(?i)(error|exception|fatal|panic|traceback|timeout|deadline exceeded|connection refused|crashloop|unavailable)"
)
SIGNAL_LINE_PATTERN = re.compile(
    r"(?i)(error|exception|fatal|panic|traceback|timeout|deadline exceeded|connection refused|unavailable|warn|throttl|oom|killed|refused|failed)"
)
SENSITIVE_ENV_PATTERN = re.compile(r"(?i)(password|passwd|secret|token|credential|api[_-]?key|private[_-]?key)")
MAX_LOG_LINES_RETURNED = 8
FORBIDDEN_SHELL_TOKENS = {"|", "||", "&", "&&", ";", ">", ">>", "<", "<<", "$(", "`"}
ALLOWED_KUBECTL_VERBS = {"get", "describe", "logs", "rollout", "delete", "patch"}
RESOURCE_LIMIT_KEYS = {"limits", "requests"}


def summarize_pod_logs(stdout: str) -> Dict[str, Any]:
    all_lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    error_lines = [line for line in all_lines if ERROR_LINE_PATTERN.search(line)]
    signal_lines = [line for line in all_lines if SIGNAL_LINE_PATTERN.search(line)]
    recent_lines = all_lines[-MAX_LOG_LINES_RETURNED:]
    return {
        "error_count": len(error_lines),
        "error_lines": error_lines[:MAX_LOG_LINES_RETURNED],
        "signal_lines": signal_lines[:MAX_LOG_LINES_RETURNED],
        "recent_lines": recent_lines,
    }


def aggregate_log_summaries(service: str, pod_summaries: List[Dict[str, Any]], errors: List[str]) -> Dict[str, Any]:
    aggregate_error_lines: List[str] = []
    aggregate_signal_lines: List[str] = []
    for item in pod_summaries:
        aggregate_error_lines.extend(item.get("error_lines", []) or [])
        aggregate_signal_lines.extend(item.get("signal_lines", []) or [])

    ordered = sorted(pod_summaries, key=lambda item: item.get("error_count", 0), reverse=True)
    primary = ordered[0] if ordered else {
        "pod_name": "",
        "error_count": 0,
        "error_lines": [],
        "signal_lines": [],
        "recent_lines": [],
    }
    return {
        "service": service,
        "pod_name": primary.get("pod_name", ""),
        "error_count": sum(item.get("error_count", 0) for item in ordered),
        "error_lines": aggregate_error_lines[:MAX_LOG_LINES_RETURNED],
        "signal_lines": aggregate_signal_lines[:MAX_LOG_LINES_RETURNED],
        "recent_lines": primary.get("recent_lines", [])[:MAX_LOG_LINES_RETURNED],
        "pods": ordered,
        "error": "; ".join(errors) if errors else None,
    }


def summarize_deployment_config(dep: Dict[str, Any]) -> Dict[str, Any]:
    template_spec = (((dep.get("spec") or {}).get("template") or {}).get("spec") or {})
    containers: List[Dict[str, Any]] = []
    flat_env: List[Dict[str, Any]] = []

    for container in template_spec.get("containers", []) or []:
        container_name = str(container.get("name", ""))
        env = summarize_container_env(container_name, container.get("env", []) or [])
        flat_env.extend(env)
        containers.append(
            {
                "name": container_name,
                "image": container.get("image", ""),
                "ports": summarize_container_ports(container),
                "env": env,
                "envFrom": summarize_env_from(container.get("envFrom", []) or []),
                "resources": container.get("resources", {}) or {},
                "readinessProbe": summarize_probe(container.get("readinessProbe", {}) or {}),
                "livenessProbe": summarize_probe(container.get("livenessProbe", {}) or {}),
                "startupProbe": summarize_probe(container.get("startupProbe", {}) or {}),
            }
        )

    return {
        "deployment": dep.get("metadata", {}).get("name", ""),
        "replicas": (dep.get("spec") or {}).get("replicas", 0),
        "containers": containers,
        "env": flat_env,
    }


def summarize_container_env(container_name: str, env_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in env_items:
        name = str(item.get("name", ""))
        row: Dict[str, Any] = {
            "container": container_name,
            "name": name,
        }
        if "value" in item:
            value = str(item.get("value", ""))
            redacted = bool(SENSITIVE_ENV_PATTERN.search(name))
            row["value"] = "<redacted>" if redacted else value
            row["value_redacted"] = redacted
        elif "valueFrom" in item:
            row["value_from"] = summarize_value_from(item.get("valueFrom", {}) or {})
        rows.append(row)
    return rows


def summarize_value_from(value_from: Dict[str, Any]) -> Dict[str, Any]:
    for key in ("configMapKeyRef", "secretKeyRef", "fieldRef", "resourceFieldRef"):
        value = value_from.get(key)
        if isinstance(value, dict):
            return {
                "type": key,
                "name": value.get("name", ""),
                "key": value.get("key", ""),
                "fieldPath": value.get("fieldPath", ""),
                "resource": value.get("resource", ""),
            }
    return {}


def summarize_env_from(env_from_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in env_from_items:
        for key in ("configMapRef", "secretRef"):
            value = item.get(key)
            if isinstance(value, dict):
                rows.append(
                    {
                        "type": key,
                        "name": value.get("name", ""),
                        "optional": value.get("optional"),
                        "prefix": item.get("prefix", ""),
                    }
                )
    return rows


def summarize_container_ports(container: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "name": port.get("name", ""),
            "containerPort": port.get("containerPort"),
            "protocol": port.get("protocol", ""),
        }
        for port in container.get("ports", []) or []
    ]


def summarize_probe(probe: Dict[str, Any]) -> Dict[str, Any]:
    if not probe:
        return {}
    row: Dict[str, Any] = {}
    for key in ("initialDelaySeconds", "periodSeconds", "timeoutSeconds", "successThreshold", "failureThreshold"):
        if key in probe:
            row[key] = probe.get(key)
    if isinstance(probe.get("httpGet"), dict):
        http_get = probe.get("httpGet", {}) or {}
        row["httpGet"] = {
            "path": http_get.get("path", ""),
            "port": http_get.get("port"),
            "scheme": http_get.get("scheme", ""),
        }
    if isinstance(probe.get("grpc"), dict):
        grpc = probe.get("grpc", {}) or {}
        row["grpc"] = {
            "port": grpc.get("port"),
            "service": grpc.get("service", ""),
        }
    if isinstance(probe.get("tcpSocket"), dict):
        row["tcpSocket"] = {"port": (probe.get("tcpSocket", {}) or {}).get("port")}
    if isinstance(probe.get("exec"), dict):
        row["exec"] = {"command": list((probe.get("exec", {}) or {}).get("command", []) or [])}
    return row


def summarize_deployment_pods(dep: Dict[str, Any], pod_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    selector = dep.get("spec", {}).get("selector", {}).get("matchLabels", {}) or {}
    deployment_config = summarize_deployment_config(dep)
    if not selector:
        return {
            "exists": True,
            "selector": {},
            "pods": [],
            "pod_count": 0,
            "ready_pod_count": 0,
            "progressing": False,
            "deployment_config": deployment_config,
        }

    pods: List[Dict[str, Any]] = []
    ready_pod_count = 0
    for item in pod_items:
        conditions = item.get("status", {}).get("conditions", []) or []
        ready = any(condition.get("type") == "Ready" and condition.get("status") == "True" for condition in conditions)
        restart_count = sum(int(status.get("restartCount", 0)) for status in item.get("status", {}).get("containerStatuses", []) or [])
        container_ports: List[Dict[str, Any]] = []
        for container in item.get("spec", {}).get("containers", []) or []:
            for port in container.get("ports", []) or []:
                container_ports.append(
                    {
                        "container": container.get("name", ""),
                        "name": port.get("name", ""),
                        "containerPort": port.get("containerPort"),
                        "protocol": port.get("protocol", ""),
                    }
                )
        if ready:
            ready_pod_count += 1
        pods.append(
            {
                "name": item.get("metadata", {}).get("name", ""),
                "phase": item.get("status", {}).get("phase", ""),
                "ready": ready,
                "restart_count": restart_count,
                "labels": item.get("metadata", {}).get("labels", {}) or {},
                "pod_ip": item.get("status", {}).get("podIP", ""),
                "container_ports": container_ports,
            }
        )

    return {
        "exists": True,
        "selector": selector,
        "pods": pods,
        "pod_count": len(pods),
        "ready_pod_count": ready_pod_count,
        "progressing": len(pods) > 0 and ready_pod_count < len(pods),
        "deployment_config": deployment_config,
    }


def injector_event(api_version: str, kind: str, name: str, reason: str, message: str) -> bool:
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


def validate_kubectl_command(tokens: List[str]) -> tuple[bool, str]:
    if not tokens:
        return False, "empty command"
    if any(token in FORBIDDEN_SHELL_TOKENS for token in tokens):
        return False, "shell operators are not allowed"
    if tokens[0] != "kubectl":
        return False, "only kubectl commands are allowed"

    verb_index = find_kubectl_verb_index(tokens)
    if verb_index is None:
        return False, "no supported kubectl verb found"

    verb = tokens[verb_index]
    if verb not in ALLOWED_KUBECTL_VERBS:
        return False, f"kubectl {verb} is not whitelisted"

    if verb in {"get", "describe", "logs"}:
        return True, ""
    if verb == "rollout":
        subcommand_index = first_non_flag_index(tokens, verb_index + 1)
        if subcommand_index is None:
            return False, "kubectl rollout requires a subcommand"
        subcommand = tokens[subcommand_index]
        if subcommand not in {"undo", "restart"}:
            return False, "only kubectl rollout undo/restart are allowed"
        return True, ""
    if verb == "delete":
        resource_index = first_non_flag_index(tokens, verb_index + 1)
        if resource_index is None:
            return False, "kubectl delete requires a resource"
        resource = tokens[resource_index]
        if resource != "pod" and not resource.startswith("pod/"):
            return False, "only kubectl delete pod is allowed"
        return True, ""
    if verb == "patch":
        return validate_patch_command(tokens[verb_index:])
    return False, "unsupported kubectl command"


def find_kubectl_verb_index(tokens: List[str]) -> int | None:
    for index, token in enumerate(tokens[1:], start=1):
        if token in ALLOWED_KUBECTL_VERBS:
            return index
    return None


def first_non_flag_index(tokens: List[str], start: int) -> int | None:
    for index in range(start, len(tokens)):
        if not tokens[index].startswith("-"):
            return index
    return None


def validate_patch_command(patch_tokens: List[str]) -> tuple[bool, str]:
    if len(patch_tokens) < 3:
        return False, "kubectl patch requires a resource target"
    patch_arg = None
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
    if not patch_only_touches_resources(payload):
        return False, "kubectl patch is restricted to container resource requests/limits"
    return True, ""


def patch_only_touches_resources(payload: Any) -> bool:
    if not isinstance(payload, dict) or "spec" not in payload:
        return False
    spec = payload.get("spec")
    if not isinstance(spec, dict):
        return False

    pod_spec = (((spec.get("template") or {}).get("spec")) if isinstance(spec.get("template"), dict) else None) if "template" in spec else spec
    if not isinstance(pod_spec, dict):
        return False
    if any(key not in {"containers", "initContainers"} for key in pod_spec.keys()):
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
            if any(key not in {"name", "resources"} for key in container.keys()):
                return False
            resources = container.get("resources")
            if not isinstance(resources, dict):
                return False
            if any(key not in RESOURCE_LIMIT_KEYS for key in resources.keys()):
                return False
    return True
