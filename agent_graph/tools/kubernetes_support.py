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


def summarize_deployment_pods(dep: Dict[str, Any], pod_items: List[Dict[str, Any]]) -> Dict[str, Any]:
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

    pods: List[Dict[str, Any]] = []
    ready_pod_count = 0
    for item in pod_items:
        conditions = item.get("status", {}).get("conditions", []) or []
        ready = any(condition.get("type") == "Ready" and condition.get("status") == "True" for condition in conditions)
        restart_count = sum(int(status.get("restartCount", 0)) for status in item.get("status", {}).get("containerStatuses", []) or [])
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
