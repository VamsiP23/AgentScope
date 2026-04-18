from __future__ import annotations

import json
import shlex
from datetime import datetime, timezone
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
                    "timestamp": self._event_timestamp(item),
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
                "deployment_config": {},
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
                "deployment_config": summarize_deployment_pods(dep, []).get("deployment_config", {}),
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
                "deployment_config": summarize_deployment_pods(dep, []).get("deployment_config", {}),
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
        service_config = self.service_config(namespace, service, kubectl_context=kubectl_context)
        service_config_summary = self._service_config_summary(service_config)
        annotated_events = self._annotate_event_ages(recent_events)
        relevant_events = self._rank_service_events(annotated_events, service_config_summary)

        pod_phases = [
            {
                "pod_name": pod.get("name", ""),
                "phase": pod.get("phase", ""),
                "ready": pod.get("ready", False),
                "restart_count": pod.get("restart_count", 0),
                "labels": pod.get("labels", {}),
                "container_ports": pod.get("container_ports", []),
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
            "service_config_summary": service_config_summary,
            "recent_events": relevant_events,
            "rollout_progressing": rollout_progressing,
            "restart_count": restart_count,
            "deployment_selector": pod_status.get("selector", {}),
            "deployment_config": pod_status.get("deployment_config", {}),
            "service_config": service_config,
            "error": error_message,
        }

    def service_config(
        self,
        namespace: str,
        service: str,
        kubectl_context: str = "",
    ) -> Dict[str, Any]:
        svc_result = run_cmd(
            self._kubectl_args(["get", "service", service, "-n", namespace, "-o", "json"], kubectl_context)
        )
        if svc_result["returncode"] != 0:
            return {
                "service": service,
                "exists": False,
                "error": svc_result["stderr"] or svc_result["stdout"],
            }

        try:
            svc = json.loads(svc_result["stdout"])
        except Exception as exc:
            return {
                "service": service,
                "exists": False,
                "error": f"failed to parse service json: {exc}",
            }

        selector = dict(svc.get("spec", {}).get("selector", {}) or {})
        ports = []
        for port in svc.get("spec", {}).get("ports", []) or []:
            ports.append(
                {
                    "name": port.get("name", ""),
                    "port": port.get("port"),
                    "targetPort": port.get("targetPort"),
                    "protocol": port.get("protocol", ""),
                }
            )

        selector_expr = ",".join(f"{key}={value}" for key, value in selector.items())
        selected_pods = self._pods_for_selector(namespace, selector_expr, kubectl_context) if selector_expr else []
        deployment_pods = self._pods_for_selector(namespace, f"app={service}", kubectl_context)
        endpoints = self._service_endpoints(namespace, service, kubectl_context)
        summary = self._service_config_summary(
            {
                "service": service,
                "exists": True,
                "selector": selector,
                "ports": ports,
                "selected_pods": selected_pods,
                "deployment_pods": deployment_pods,
                "endpoints": endpoints,
                "error": None,
            }
        )

        return {
            "service": service,
            "exists": True,
            "selector": selector,
            "ports": ports,
            "selected_pods": selected_pods,
            "deployment_pods": deployment_pods,
            "endpoints": endpoints,
            "summary": summary,
            "error": None,
        }

    def _service_config_summary(self, service_config: Dict[str, Any]) -> Dict[str, Any]:
        if not service_config or not service_config.get("exists", False):
            return {
                "service": str(service_config.get("service", "")) if service_config else "",
                "exists": False,
                "anomalies": ["service_config_unavailable"],
                "error": service_config.get("error") if service_config else "service config missing",
            }

        selected_pods = list(service_config.get("selected_pods", []) or [])
        deployment_pods = list(service_config.get("deployment_pods", []) or [])
        endpoints = dict(service_config.get("endpoints", {}) or {})
        endpoint_slices = list(endpoints.get("endpoint_slices", []) or [])
        ports = list(service_config.get("ports", []) or [])
        container_ports = self._container_ports_by_name(deployment_pods)
        service_port_alignment = self._service_port_alignment(ports, container_ports)
        anomalies: List[str] = []

        selector = dict(service_config.get("selector", {}) or {})
        selector_present = bool(selector)
        if selector_present and not selected_pods and deployment_pods:
            anomalies.append("service_selector_matches_no_pods")
        if not selector_present:
            anomalies.append("service_has_no_selector")

        ready_from_slices = 0
        not_ready_from_slices = 0
        for item in endpoint_slices:
            for endpoint in item.get("endpoints", []) or []:
                if endpoint.get("ready") is True:
                    ready_from_slices += 1
                elif endpoint.get("ready") is False:
                    not_ready_from_slices += 1

        raw_ready = int(endpoints.get("ready_addresses", 0) or 0)
        raw_not_ready = int(endpoints.get("not_ready_addresses", 0) or 0)
        effective_ready = ready_from_slices if endpoint_slices else raw_ready
        effective_not_ready = not_ready_from_slices if endpoint_slices else raw_not_ready
        if selector_present and not selected_pods:
            effective_ready = 0
            effective_not_ready = 0
            if raw_ready or ready_from_slices:
                anomalies.append("endpoint_cache_stale_for_current_selector")
        if effective_ready == 0:
            anomalies.append("service_has_no_effective_ready_endpoints")

        if not service_port_alignment.get("aligned", True):
            anomalies.append("service_target_port_mismatch")

        return {
            "service": service_config.get("service", ""),
            "exists": True,
            "selector": selector,
            "selected_pod_count": len(selected_pods),
            "deployment_pod_count": len(deployment_pods),
            "deployment_pod_labels": [
                {
                    "name": pod.get("name", ""),
                    "labels": pod.get("labels", {}),
                    "ready": bool(pod.get("ready", False)),
                }
                for pod in deployment_pods[:5]
            ],
            "service_ports": ports,
            "container_ports": container_ports,
            "endpoint_counts": {
                "effective_ready": effective_ready,
                "effective_not_ready": effective_not_ready,
                "raw_endpoints_ready": raw_ready,
                "raw_endpoints_not_ready": raw_not_ready,
                "endpoint_slice_ready": ready_from_slices,
                "endpoint_slice_not_ready": not_ready_from_slices,
            },
            "service_port_alignment": service_port_alignment,
            "anomalies": anomalies,
            "takeaway": self._service_config_takeaway(selector, selected_pods, deployment_pods, service_port_alignment, anomalies),
        }

    def _container_ports_by_name(self, pods: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        rows: List[Dict[str, Any]] = []
        for pod in pods:
            for port in pod.get("container_ports", []) or []:
                key = (
                    port.get("container", ""),
                    port.get("name", ""),
                    port.get("containerPort"),
                    port.get("protocol", ""),
                )
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "container": key[0],
                        "name": key[1],
                        "containerPort": key[2],
                        "protocol": key[3],
                    }
                )
        return rows

    def _service_port_alignment(self, service_ports: List[Dict[str, Any]], container_ports: List[Dict[str, Any]]) -> Dict[str, Any]:
        port_numbers = {int(port.get("containerPort")) for port in container_ports if self._is_int_like(port.get("containerPort"))}
        named_ports = {str(port.get("name")) for port in container_ports if str(port.get("name", "")).strip()}
        mismatches: List[Dict[str, Any]] = []
        for service_port in service_ports:
            target_port = service_port.get("targetPort")
            if self._is_int_like(target_port):
                if int(target_port) not in port_numbers:
                    mismatches.append(
                        {
                            "service_port": service_port.get("port"),
                            "targetPort": target_port,
                            "reason": "numeric targetPort is not exposed by any selected deployment pod container",
                        }
                    )
            elif str(target_port).strip() and str(target_port).strip() not in named_ports:
                mismatches.append(
                    {
                        "service_port": service_port.get("port"),
                        "targetPort": target_port,
                        "reason": "named targetPort is not exposed by any selected deployment pod container",
                    }
                )
        return {
            "aligned": not mismatches,
            "mismatches": mismatches,
        }

    def _service_config_takeaway(
        self,
        selector: Dict[str, Any],
        selected_pods: List[Dict[str, Any]],
        deployment_pods: List[Dict[str, Any]],
        service_port_alignment: Dict[str, Any],
        anomalies: List[str],
    ) -> str:
        if "service_selector_matches_no_pods" in anomalies:
            labels = [pod.get("labels", {}) for pod in deployment_pods[:3]]
            return f"Service selector {selector} selects 0 pods while deployment pods exist with labels {labels}"
        if "service_target_port_mismatch" in anomalies:
            return f"Service targetPort does not match exposed deployment container ports: {service_port_alignment.get('mismatches', [])}"
        if not selected_pods:
            return "Service currently selects no pods"
        return "Service selector, endpoint, and targetPort evidence has no obvious mismatch"

    def _rank_service_events(self, events: List[Dict[str, Any]], service_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not events:
            return []
        has_config_anomaly = bool(service_summary.get("anomalies"))

        def score(event: Dict[str, Any]) -> tuple:
            age = float(event.get("age_seconds", 0.0) or 0.0)
            reason = str(event.get("reason", "")).lower()
            message = str(event.get("message", "")).lower()
            event_type = str(event.get("type", "")).lower()
            config_noise = (
                "unhealthy" in reason
                or "failedcreate" in reason
                or "service account" in message
                or "serviceaccount" in message
            )
            stale_penalty = 2 if has_config_anomaly and (event.get("stale", False) or config_noise) else 0
            warning_rank = 0 if event_type == "warning" else 1
            freshness_rank = 0 if age <= 900 else 1
            failure_rank = 0 if ("fail" in reason or "backoff" in reason or "unhealthy" in reason) else 1
            return (stale_penalty, freshness_rank, warning_rank, failure_rank, age)

        return sorted(events, key=score)[:6]

    def _annotate_event_ages(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        now = datetime.now(timezone.utc)
        rows: List[Dict[str, Any]] = []
        for event in events:
            row = dict(event)
            timestamp = str(row.get("timestamp", "") or "")
            age_seconds = None
            if timestamp:
                try:
                    age_seconds = max(0.0, (now - datetime.fromisoformat(timestamp.replace("Z", "+00:00"))).total_seconds())
                except ValueError:
                    age_seconds = None
            if age_seconds is not None:
                row["age_seconds"] = round(age_seconds, 3)
                row["stale"] = age_seconds > 900
            else:
                row["stale"] = False
            rows.append(row)
        return rows

    def _event_timestamp(self, event: Dict[str, Any]) -> str:
        for key in ("eventTime", "lastTimestamp", "firstTimestamp"):
            value = str(event.get(key, "") or "")
            if value:
                return value
        value = str(event.get("metadata", {}).get("creationTimestamp", "") or "")
        return value

    def _is_int_like(self, value: Any) -> bool:
        try:
            int(value)
            return True
        except (TypeError, ValueError):
            return False

    def _pods_for_selector(
        self,
        namespace: str,
        selector_expr: str,
        kubectl_context: str = "",
    ) -> List[Dict[str, Any]]:
        result = run_cmd(
            self._kubectl_args(["get", "pods", "-n", namespace, "-l", selector_expr, "-o", "json"], kubectl_context)
        )
        if result["returncode"] != 0:
            return []
        try:
            pod_items = json.loads(result["stdout"]).get("items", [])
        except Exception:
            return []
        return [self._pod_network_summary(item) for item in pod_items]

    def _service_endpoints(
        self,
        namespace: str,
        service: str,
        kubectl_context: str = "",
    ) -> Dict[str, Any]:
        endpoint_result = run_cmd(
            self._kubectl_args(["get", "endpoints", service, "-n", namespace, "-o", "json"], kubectl_context)
        )
        endpoint_slices_result = run_cmd(
            self._kubectl_args(
                [
                    "get",
                    "endpointslices",
                    "-n",
                    namespace,
                    "-l",
                    f"kubernetes.io/service-name={service}",
                    "-o",
                    "json",
                ],
                kubectl_context,
            )
        )

        ready_addresses = 0
        not_ready_addresses = 0
        subsets: List[Dict[str, Any]] = []
        if endpoint_result["returncode"] == 0:
            try:
                endpoint_payload = json.loads(endpoint_result["stdout"])
                for subset in endpoint_payload.get("subsets", []) or []:
                    addresses = subset.get("addresses", []) or []
                    not_ready = subset.get("notReadyAddresses", []) or []
                    ready_addresses += len(addresses)
                    not_ready_addresses += len(not_ready)
                    subsets.append(
                        {
                            "ports": [
                                {
                                    "name": port.get("name", ""),
                                    "port": port.get("port"),
                                    "protocol": port.get("protocol", ""),
                                }
                                for port in subset.get("ports", []) or []
                            ],
                            "ready_addresses": [
                                {
                                    "ip": address.get("ip", ""),
                                    "target_ref": (address.get("targetRef", {}) or {}).get("name", ""),
                                }
                                for address in addresses
                            ],
                            "not_ready_addresses": [
                                {
                                    "ip": address.get("ip", ""),
                                    "target_ref": (address.get("targetRef", {}) or {}).get("name", ""),
                                }
                                for address in not_ready
                            ],
                        }
                    )
            except Exception:
                pass

        slices: List[Dict[str, Any]] = []
        if endpoint_slices_result["returncode"] == 0:
            try:
                slice_payload = json.loads(endpoint_slices_result["stdout"])
                for item in slice_payload.get("items", []) or []:
                    endpoints = []
                    for endpoint in item.get("endpoints", []) or []:
                        conditions = endpoint.get("conditions", {}) or {}
                        endpoints.append(
                            {
                                "addresses": list(endpoint.get("addresses", []) or []),
                                "ready": conditions.get("ready"),
                                "serving": conditions.get("serving"),
                                "terminating": conditions.get("terminating"),
                                "target_ref": (endpoint.get("targetRef", {}) or {}).get("name", ""),
                            }
                        )
                    slices.append(
                        {
                            "name": item.get("metadata", {}).get("name", ""),
                            "ports": [
                                {
                                    "name": port.get("name", ""),
                                    "port": port.get("port"),
                                    "protocol": port.get("protocol", ""),
                                }
                                for port in item.get("ports", []) or []
                            ],
                            "endpoints": endpoints,
                        }
                    )
            except Exception:
                pass

        return {
            "ready_addresses": ready_addresses,
            "not_ready_addresses": not_ready_addresses,
            "subsets": subsets,
            "endpoint_slices": slices,
            "endpoints_error": None if endpoint_result["returncode"] == 0 else endpoint_result["stderr"] or endpoint_result["stdout"],
            "endpoint_slices_error": (
                None
                if endpoint_slices_result["returncode"] == 0
                else endpoint_slices_result["stderr"] or endpoint_slices_result["stdout"]
            ),
        }

    def _pod_network_summary(self, pod: Dict[str, Any]) -> Dict[str, Any]:
        conditions = pod.get("status", {}).get("conditions", []) or []
        ready = any(condition.get("type") == "Ready" and condition.get("status") == "True" for condition in conditions)
        ports: List[Dict[str, Any]] = []
        for container in pod.get("spec", {}).get("containers", []) or []:
            for port in container.get("ports", []) or []:
                ports.append(
                    {
                        "container": container.get("name", ""),
                        "name": port.get("name", ""),
                        "containerPort": port.get("containerPort"),
                        "protocol": port.get("protocol", ""),
                    }
                )
        return {
            "name": pod.get("metadata", {}).get("name", ""),
            "labels": dict(pod.get("metadata", {}).get("labels", {}) or {}),
            "phase": pod.get("status", {}).get("phase", ""),
            "ready": ready,
            "pod_ip": pod.get("status", {}).get("podIP", ""),
            "container_ports": ports,
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
