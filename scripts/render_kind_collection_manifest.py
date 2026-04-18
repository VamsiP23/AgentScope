#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, Iterable, List

import yaml


APP_DEPLOYMENTS = {
    "adservice",
    "cartservice",
    "checkoutservice",
    "currencyservice",
    "emailservice",
    "frontend",
    "paymentservice",
    "productcatalogservice",
    "recommendationservice",
    "shippingservice",
}

CLUSTER_SCOPED_KINDS = {
    "ClusterRole",
    "ClusterRoleBinding",
    "CustomResourceDefinition",
    "Namespace",
    "Node",
    "PersistentVolume",
    "StorageClass",
}

RESOURCE_PROFILES: Dict[str, Dict[str, Dict[str, str]]] = {
    "adservice": {
        "requests": {"cpu": "250m", "memory": "256Mi"},
        "limits": {"cpu": "750m", "memory": "512Mi"},
    },
    "cartservice": {
        "requests": {"cpu": "250m", "memory": "128Mi"},
        "limits": {"cpu": "1000m", "memory": "512Mi"},
    },
    "checkoutservice": {
        "requests": {"cpu": "250m", "memory": "128Mi"},
        "limits": {"cpu": "600m", "memory": "256Mi"},
    },
    "frontend": {
        "requests": {"cpu": "250m", "memory": "128Mi"},
        "limits": {"cpu": "600m", "memory": "256Mi"},
    },
    "recommendationservice": {
        "requests": {"cpu": "200m", "memory": "256Mi"},
        "limits": {"cpu": "500m", "memory": "512Mi"},
    },
}

DEFAULT_APP_RESOURCES = {
    "requests": {"cpu": "200m", "memory": "128Mi"},
    "limits": {"cpu": "500m", "memory": "256Mi"},
}

OBSERVABILITY_RESOURCES: Dict[str, Dict[str, Dict[str, str]]] = {
    "prometheus": {
        "requests": {"cpu": "200m", "memory": "512Mi"},
        "limits": {"cpu": "1000m", "memory": "1536Mi"},
    },
    "jaeger": {
        "requests": {"cpu": "250m", "memory": "512Mi"},
        "limits": {"cpu": "1500m", "memory": "2Gi"},
    },
    "opentelemetrycollector": {
        "requests": {"cpu": "200m", "memory": "384Mi"},
        "limits": {"cpu": "1000m", "memory": "1Gi"},
    },
    "kube-state-metrics": {
        "requests": {"cpu": "50m", "memory": "128Mi"},
        "limits": {"cpu": "300m", "memory": "256Mi"},
    },
    "grafana": {
        "requests": {"cpu": "50m", "memory": "128Mi"},
        "limits": {"cpu": "300m", "memory": "384Mi"},
    },
}

NODEPORTS = {
    "frontend-external": ("http", 80, 8080, 30080),
    "prometheus": ("web", 9090, 9090, 30090),
    "grafana": ("web", 3000, 3000, 30300),
}


def load_yaml_documents(paths: Iterable[Path]) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for doc in yaml.safe_load_all(handle):
                if isinstance(doc, dict):
                    docs.append(doc)
    return docs


def container_list(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    return (
        doc.setdefault("spec", {})
        .setdefault("template", {})
        .setdefault("spec", {})
        .setdefault("containers", [])
    )


def set_env(container: Dict[str, Any], values: Dict[str, str]) -> None:
    existing = {entry.get("name"): entry for entry in container.setdefault("env", []) if isinstance(entry, dict)}
    for name, value in values.items():
        if name in existing:
            existing[name]["value"] = value
        else:
            container["env"].append({"name": name, "value": value})


def relax_probe(probe: Dict[str, Any], *, initial_delay: int, timeout: int = 10) -> None:
    probe["initialDelaySeconds"] = max(int(probe.get("initialDelaySeconds", 0) or 0), initial_delay)
    probe["timeoutSeconds"] = timeout
    probe["periodSeconds"] = 10
    probe["failureThreshold"] = 12


def patch_app_deployment(doc: Dict[str, Any], namespace: str) -> None:
    name = doc.get("metadata", {}).get("name", "")
    spec = doc.setdefault("spec", {})
    spec["replicas"] = 0 if name == "loadgenerator" else 1
    if name not in APP_DEPLOYMENTS:
        return

    for container in container_list(doc):
        resources = RESOURCE_PROFILES.get(name, DEFAULT_APP_RESOURCES)
        container["resources"] = resources
        set_env(
            container,
            {
                "ENABLE_TRACING": "1",
                "ENABLE_STATS": "1",
                "COLLECTOR_SERVICE_ADDR": "opentelemetrycollector:4317",
                "OTEL_SERVICE_NAME": name,
                "OTEL_RESOURCE_ATTRIBUTES": f"service.name={name},deployment.environment=kind",
            },
        )
        if isinstance(container.get("readinessProbe"), dict):
            relax_probe(container["readinessProbe"], initial_delay=35 if name == "cartservice" else 25)
        if isinstance(container.get("livenessProbe"), dict):
            relax_probe(container["livenessProbe"], initial_delay=60 if name == "cartservice" else 45)

        if name == "frontend":
            for probe_name in ("readinessProbe", "livenessProbe"):
                probe = container.get(probe_name)
                if isinstance(probe, dict) and isinstance(probe.get("httpGet"), dict):
                    headers = probe["httpGet"].setdefault("httpHeaders", [])
                    if not any(h.get("name", "").lower() == "cookie" for h in headers if isinstance(h, dict)):
                        headers.append({"name": "Cookie", "value": f"shop_session-id=x-{probe_name}"})


def patch_observability_deployment(doc: Dict[str, Any]) -> None:
    name = doc.get("metadata", {}).get("name", "")
    resources = OBSERVABILITY_RESOURCES.get(name)
    if not resources:
        return
    doc.setdefault("spec", {})["replicas"] = 1
    for container in container_list(doc):
        container["resources"] = resources
        if isinstance(container.get("readinessProbe"), dict):
            relax_probe(container["readinessProbe"], initial_delay=20)
        if isinstance(container.get("livenessProbe"), dict):
            relax_probe(container["livenessProbe"], initial_delay=45)


def patch_service(doc: Dict[str, Any]) -> None:
    name = doc.get("metadata", {}).get("name", "")
    spec = doc.setdefault("spec", {})
    if name in NODEPORTS:
        port_name, port, target_port, node_port = NODEPORTS[name]
        spec["type"] = "NodePort"
        spec["ports"] = [
            {
                "name": port_name,
                "port": port,
                "targetPort": target_port,
                "nodePort": node_port,
            }
        ]
    elif name == "jaeger":
        spec["type"] = "NodePort"
        ports = spec.setdefault("ports", [])
        for port in ports:
            if port.get("name") == "ui" or port.get("port") == 16686:
                port["nodePort"] = 30686


def patch_namespace_subjects(doc: Dict[str, Any], namespace: str) -> None:
    if doc.get("kind") != "ClusterRoleBinding":
        return
    for subject in doc.get("subjects", []) or []:
        if isinstance(subject, dict) and subject.get("kind") == "ServiceAccount":
            subject["namespace"] = namespace


def render(args: argparse.Namespace) -> List[Dict[str, Any]]:
    observability_paths = sorted(Path(args.observability_dir).glob("*.yaml"))
    docs = load_yaml_documents([Path(args.app_manifest), *observability_paths])

    for doc in docs:
        metadata = doc.setdefault("metadata", {})
        kind = doc.get("kind")
        if kind not in CLUSTER_SCOPED_KINDS:
            metadata.setdefault("namespace", args.namespace)
        if kind == "Deployment":
            patch_app_deployment(doc, args.namespace)
            patch_observability_deployment(doc)
        elif kind == "Service":
            patch_service(doc)
        patch_namespace_subjects(doc, args.namespace)

    return docs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render a stable kind manifest for AgentScope collection.")
    parser.add_argument("--app-manifest", default="vendor/microservices-demo/release/kubernetes-manifests.yaml")
    parser.add_argument("--observability-dir", default="observability/manifests")
    parser.add_argument("--namespace", default="default")
    parser.add_argument("--out", default=".runtime/kind_collection_manifest.yaml")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    docs = render(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        yaml.safe_dump_all(docs, handle, sort_keys=False)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
