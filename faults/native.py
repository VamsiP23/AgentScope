from __future__ import annotations

import argparse
import json
import re
import subprocess
from copy import deepcopy
from typing import Any


STATE_LABEL_KEY = "agentscope.dev/native-fault"
STATE_LABEL_VALUE = "true"


def _run_kubectl(args: list[str], *, input_text: str | None = None) -> str:
    proc = subprocess.run(
        ["kubectl", *args],
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        message = proc.stderr.strip() or proc.stdout.strip() or "kubectl failed"
        raise RuntimeError(message)
    return proc.stdout.strip()


def _kubectl_json(args: list[str]) -> dict[str, Any]:
    output = _run_kubectl([*args, "-o", "json"])
    return json.loads(output)


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    cleaned = re.sub(r"-+", "-", cleaned)
    return cleaned[:50].strip("-") or "fault"


def _state_name(spec: dict[str, Any]) -> str:
    explicit = spec.get("id") or spec.get("name") or spec.get("type") or "fault"
    return f"agentscope-native-{_safe_name(str(explicit))}"


def _container_index(deployment: dict[str, Any], container_name: str | None) -> int:
    containers = deployment["spec"]["template"]["spec"].get("containers", [])
    if not containers:
        raise RuntimeError("deployment has no containers")
    if not container_name:
        return 0
    for idx, container in enumerate(containers):
        if container.get("name") == container_name:
            return idx
    raise RuntimeError(f"container not found: {container_name}")


def _json_pointer_escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _patch_json(namespace: str, resource: str, name: str, patch: list[dict[str, Any]]) -> None:
    _run_kubectl(
        [
            "patch",
            resource,
            name,
            "-n",
            namespace,
            "--type",
            "json",
            "-p",
            json.dumps(patch),
        ]
    )


def _patch_merge(namespace: str, resource: str, name: str, patch: dict[str, Any]) -> None:
    _run_kubectl(
        [
            "patch",
            resource,
            name,
            "-n",
            namespace,
            "--type",
            "merge",
            "-p",
            json.dumps(patch),
        ]
    )


def _save_state(namespace: str, name: str, state: dict[str, Any]) -> None:
    manifest = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": {STATE_LABEL_KEY: STATE_LABEL_VALUE},
        },
        "data": {"state.json": json.dumps(state, sort_keys=True)},
    }
    _run_kubectl(["apply", "-f", "-"], input_text=json.dumps(manifest))


def _load_state(namespace: str, name: str) -> dict[str, Any] | None:
    try:
        payload = _kubectl_json(["get", "configmap", name, "-n", namespace])
    except RuntimeError as exc:
        if "NotFound" in str(exc) or "not found" in str(exc):
            return None
        raise
    data = payload.get("data", {})
    raw = data.get("state.json")
    if not raw:
        raise RuntimeError(f"state configmap {name} does not contain state.json")
    return json.loads(raw)


def _delete_state(namespace: str, name: str) -> None:
    _run_kubectl(["delete", "configmap", name, "-n", namespace, "--ignore-not-found=true"])


def _deployment(namespace: str, name: str) -> dict[str, Any]:
    return _kubectl_json(["get", "deployment", name, "-n", namespace])


def _container_patch_path(index: int, field: str) -> str:
    return f"/spec/template/spec/containers/{index}/{_json_pointer_escape(field)}"


def _patch_container_field(
    namespace: str,
    deployment_name: str,
    container_index: int,
    field: str,
    value: Any,
    *,
    existed: bool,
) -> None:
    op = "replace" if existed else "add"
    _patch_json(
        namespace,
        "deployment",
        deployment_name,
        [{"op": op, "path": _container_patch_path(container_index, field), "value": value}],
    )


def _remove_container_field(namespace: str, deployment_name: str, container_index: int, field: str) -> None:
    _patch_json(
        namespace,
        "deployment",
        deployment_name,
        [{"op": "remove", "path": _container_patch_path(container_index, field)}],
    )


def _apply_deployment_env(namespace: str, spec: dict[str, Any]) -> dict[str, Any]:
    deployment_name = str(spec["deployment"])
    container_name = spec.get("container")
    env_name = str(spec["env_name"])
    env_value = str(spec.get("env_value", ""))
    deployment = _deployment(namespace, deployment_name)
    idx = _container_index(deployment, container_name)
    container = deployment["spec"]["template"]["spec"]["containers"][idx]
    original_env = deepcopy(container.get("env"))
    env = deepcopy(original_env or [])
    replaced = False
    for item in env:
        if item.get("name") == env_name:
            item.clear()
            item.update({"name": env_name, "value": env_value})
            replaced = True
            break
    if not replaced:
        env.append({"name": env_name, "value": env_value})
    _patch_container_field(namespace, deployment_name, idx, "env", env, existed=original_env is not None)
    return {
        "type": "deployment_env",
        "deployment": deployment_name,
        "container": container_name,
        "container_index": idx,
        "original_env": original_env,
    }


def _apply_deployment_image(namespace: str, spec: dict[str, Any]) -> dict[str, Any]:
    deployment_name = str(spec["deployment"])
    deployment = _deployment(namespace, deployment_name)
    idx = _container_index(deployment, spec.get("container"))
    container = deployment["spec"]["template"]["spec"]["containers"][idx]
    original_image = container.get("image")
    _patch_container_field(
        namespace,
        deployment_name,
        idx,
        "image",
        str(spec["image"]),
        existed="image" in container,
    )
    return {
        "type": "deployment_image",
        "deployment": deployment_name,
        "container": spec.get("container"),
        "container_index": idx,
        "original_image": original_image,
    }


def _apply_deployment_probe(namespace: str, spec: dict[str, Any]) -> dict[str, Any]:
    deployment_name = str(spec["deployment"])
    probe_field = str(spec.get("probe", "readinessProbe"))
    if probe_field not in {"readinessProbe", "livenessProbe"}:
        raise RuntimeError("deployment_probe.probe must be readinessProbe or livenessProbe")
    deployment = _deployment(namespace, deployment_name)
    idx = _container_index(deployment, spec.get("container"))
    container = deployment["spec"]["template"]["spec"]["containers"][idx]
    original_probe = deepcopy(container.get(probe_field))
    if "value" in spec:
        next_probe = deepcopy(spec["value"])
    else:
        if original_probe is None:
            raise RuntimeError("probe value is required when the target container has no existing probe")
        next_probe = deepcopy(original_probe)
        if "http_path" in spec:
            next_probe.setdefault("httpGet", {})["path"] = str(spec["http_path"])
        if "tcp_port" in spec:
            next_probe["tcpSocket"] = {"port": spec["tcp_port"]}
            next_probe.pop("httpGet", None)
            next_probe.pop("grpc", None)
            next_probe.pop("exec", None)
        if "initial_delay_seconds" in spec:
            next_probe["initialDelaySeconds"] = int(spec["initial_delay_seconds"])
    _patch_container_field(
        namespace,
        deployment_name,
        idx,
        probe_field,
        next_probe,
        existed=original_probe is not None,
    )
    return {
        "type": "deployment_probe",
        "deployment": deployment_name,
        "container": spec.get("container"),
        "container_index": idx,
        "probe": probe_field,
        "original_probe": original_probe,
    }


def _apply_deployment_resources(namespace: str, spec: dict[str, Any]) -> dict[str, Any]:
    deployment_name = str(spec["deployment"])
    deployment = _deployment(namespace, deployment_name)
    idx = _container_index(deployment, spec.get("container"))
    container = deployment["spec"]["template"]["spec"]["containers"][idx]
    original_resources = deepcopy(container.get("resources"))
    resources = deepcopy(spec["resources"])
    _patch_container_field(
        namespace,
        deployment_name,
        idx,
        "resources",
        resources,
        existed=original_resources is not None,
    )
    return {
        "type": "deployment_resources",
        "deployment": deployment_name,
        "container": spec.get("container"),
        "container_index": idx,
        "original_resources": original_resources,
    }


def _apply_deployment_scale(namespace: str, spec: dict[str, Any]) -> dict[str, Any]:
    deployment_name = str(spec["deployment"])
    deployment = _deployment(namespace, deployment_name)
    original_replicas = deployment.get("spec", {}).get("replicas")
    replicas = int(spec["replicas"])
    _run_kubectl(["scale", "deployment", deployment_name, "-n", namespace, f"--replicas={replicas}"])
    return {
        "type": "deployment_scale",
        "deployment": deployment_name,
        "original_replicas": original_replicas,
    }


def _apply_pod_delete(namespace: str, spec: dict[str, Any]) -> dict[str, Any]:
    selector = str(spec["selector"])
    extra = []
    if spec.get("limit"):
        extra = ["--field-selector=status.phase=Running"]
    pods = _kubectl_json(["get", "pods", "-n", namespace, "-l", selector])
    names = [item["metadata"]["name"] for item in pods.get("items", [])]
    if not names:
        raise RuntimeError(f"no pods matched selector {selector}")
    if spec.get("limit"):
        names = names[: int(spec["limit"])]
    _run_kubectl(["delete", "pod", "-n", namespace, *names, "--wait=false"])
    return {"type": "pod_delete", "selector": selector, "deleted_pods": names, "field_selector_args": extra}


def _apply_service_selector(namespace: str, spec: dict[str, Any]) -> dict[str, Any]:
    service_name = str(spec["service"])
    service = _kubectl_json(["get", "service", service_name, "-n", namespace])
    original_selector = deepcopy(service.get("spec", {}).get("selector"))
    _patch_merge(namespace, "service", service_name, {"spec": {"selector": deepcopy(spec["selector"])}})
    return {
        "type": "service_selector",
        "service": service_name,
        "original_selector": original_selector,
    }


def _apply_service_ports(namespace: str, spec: dict[str, Any]) -> dict[str, Any]:
    service_name = str(spec["service"])
    service = _kubectl_json(["get", "service", service_name, "-n", namespace])
    original_ports = deepcopy(service.get("spec", {}).get("ports", []))
    ports = deepcopy(original_ports)
    index = int(spec.get("port_index", 0))
    if index >= len(ports):
        raise RuntimeError(f"service {service_name} has no port at index {index}")
    if "target_port" in spec:
        ports[index]["targetPort"] = spec["target_port"]
    if "port" in spec:
        ports[index]["port"] = int(spec["port"])
    _patch_merge(namespace, "service", service_name, {"spec": {"ports": ports}})
    return {
        "type": "service_ports",
        "service": service_name,
        "original_ports": original_ports,
    }


def _apply_stress_job(namespace: str, spec: dict[str, Any]) -> dict[str, Any]:
    name = str(spec.get("job_name") or f"{_state_name(spec)}-job")[:63].strip("-")
    image = str(spec.get("image", "busybox:1.36"))
    command = spec.get("command")
    args = spec.get("args")
    if command is not None and (not isinstance(command, list) or not all(isinstance(item, str) for item in command)):
        raise RuntimeError("stress_job.command must be a list of strings")
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise RuntimeError("stress_job.args must be a list of strings")
    labels = {
        "app": name,
        "agentscope.dev/fault-type": "stress-job",
        STATE_LABEL_KEY: STATE_LABEL_VALUE,
    }
    manifest = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": name, "namespace": namespace, "labels": labels},
        "spec": {
            "backoffLimit": 0,
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "restartPolicy": "Never",
                    "containers": [
                        {
                            "name": "stress",
                            "image": image,
                            "resources": deepcopy(spec.get("resources", {})),
                        }
                    ],
                },
            },
        },
    }
    container = manifest["spec"]["template"]["spec"]["containers"][0]
    if command is not None:
        container["command"] = command
    container["args"] = args
    if spec.get("node_selector"):
        manifest["spec"]["template"]["spec"]["nodeSelector"] = deepcopy(spec["node_selector"])
    _run_kubectl(["apply", "-f", "-"], input_text=json.dumps(manifest))
    return {"type": "stress_job", "job_name": name}


APPLY_HANDLERS = {
    "deployment_env": _apply_deployment_env,
    "deployment_image": _apply_deployment_image,
    "deployment_probe": _apply_deployment_probe,
    "deployment_resources": _apply_deployment_resources,
    "deployment_scale": _apply_deployment_scale,
    "pod_delete": _apply_pod_delete,
    "service_selector": _apply_service_selector,
    "service_ports": _apply_service_ports,
    "stress_job": _apply_stress_job,
}


def apply_fault(namespace: str, spec: dict[str, Any]) -> dict[str, Any]:
    fault_type = str(spec.get("type", ""))
    if fault_type not in APPLY_HANDLERS:
        supported = ", ".join(sorted(APPLY_HANDLERS))
        raise RuntimeError(f"unsupported native fault type {fault_type!r}; supported: {supported}")
    state_name = _state_name(spec)
    existing = _load_state(namespace, state_name)
    if existing is not None:
        raise RuntimeError(f"native fault state already exists: {state_name}; revert it before reapplying")
    state = APPLY_HANDLERS[fault_type](namespace, spec)
    state["state_name"] = state_name
    state["fault_spec"] = deepcopy(spec)
    _save_state(namespace, state_name, state)
    return state


def revert_fault(namespace: str, spec: dict[str, Any]) -> dict[str, Any]:
    state_name = _state_name(spec)
    state = _load_state(namespace, state_name)
    if state is None:
        return {"state_name": state_name, "reverted": False, "reason": "state not found"}
    fault_type = state.get("type")
    if fault_type == "deployment_env":
        original = state.get("original_env")
        if original is None:
            _remove_container_field(namespace, state["deployment"], int(state["container_index"]), "env")
        else:
            _patch_container_field(
                namespace,
                state["deployment"],
                int(state["container_index"]),
                "env",
                original,
                existed=True,
            )
    elif fault_type == "deployment_image":
        _patch_container_field(
            namespace,
            state["deployment"],
            int(state["container_index"]),
            "image",
            state["original_image"],
            existed=True,
        )
    elif fault_type == "deployment_probe":
        original = state.get("original_probe")
        if original is None:
            _remove_container_field(namespace, state["deployment"], int(state["container_index"]), state["probe"])
        else:
            _patch_container_field(
                namespace,
                state["deployment"],
                int(state["container_index"]),
                state["probe"],
                original,
                existed=True,
            )
    elif fault_type == "deployment_resources":
        original = state.get("original_resources")
        if original is None:
            _remove_container_field(namespace, state["deployment"], int(state["container_index"]), "resources")
        else:
            _patch_container_field(
                namespace,
                state["deployment"],
                int(state["container_index"]),
                "resources",
                original,
                existed=True,
            )
    elif fault_type == "deployment_scale":
        replicas = state.get("original_replicas")
        if replicas is not None:
            _run_kubectl(
                [
                    "scale",
                    "deployment",
                    state["deployment"],
                    "-n",
                    namespace,
                    f"--replicas={int(replicas)}",
                ]
            )
    elif fault_type == "pod_delete":
        pass
    elif fault_type == "service_selector":
        _patch_merge(
            namespace,
            "service",
            state["service"],
            {"spec": {"selector": state.get("original_selector") or {}}},
        )
    elif fault_type == "service_ports":
        _patch_merge(
            namespace,
            "service",
            state["service"],
            {"spec": {"ports": state.get("original_ports", [])}},
        )
    elif fault_type == "stress_job":
        _run_kubectl(["delete", "job", state["job_name"], "-n", namespace, "--ignore-not-found=true"])
        _run_kubectl(
            [
                "delete",
                "pod",
                "-n",
                namespace,
                "-l",
                f"job-name={state['job_name']}",
                "--ignore-not-found=true",
            ]
        )
    else:
        raise RuntimeError(f"cannot revert unsupported saved native fault type: {fault_type}")
    _delete_state(namespace, state_name)
    state["reverted"] = True
    return state


def _parse_spec(args: argparse.Namespace) -> dict[str, Any]:
    if args.spec_json:
        payload = json.loads(args.spec_json)
    else:
        payload = json.load(args.spec_file)
    if not isinstance(payload, dict):
        raise RuntimeError("native fault spec must be a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply or revert native Kubernetes AgentScope faults.")
    parser.add_argument("action", choices=["apply", "revert"])
    parser.add_argument("--namespace", default="default")
    parser.add_argument("--spec-json", default="")
    parser.add_argument("--spec-file", type=argparse.FileType("r"))
    args = parser.parse_args()
    if not args.spec_json and args.spec_file is None:
        parser.error("--spec-json or --spec-file is required")
    try:
        spec = _parse_spec(args)
        if args.action == "apply":
            result = apply_fault(args.namespace, spec)
        else:
            result = revert_fault(args.namespace, spec)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
