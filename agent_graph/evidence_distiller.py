from __future__ import annotations

import re
from collections import Counter
from copy import deepcopy
from typing import Any, Dict, Iterable, List


EVIDENCE_TOOLS = {
    "get_k8s_state",
    "get_metrics",
    "get_logs",
    "get_traces",
    "get_dependency_traces",
    "get_cluster_resource_context",
}


class EvidenceDistiller:
    """Deterministic compact views for raw ACI/replay evidence outputs."""

    def distill(self, tool: str, output: Dict[str, Any]) -> Dict[str, Any]:
        method = str(tool).strip()
        raw = deepcopy(output or {})
        if method not in EVIDENCE_TOOLS:
            return raw

        if method == "get_k8s_state":
            view = self._k8s_state(raw)
        elif method == "get_metrics":
            view = self._metrics(raw)
        elif method == "get_logs":
            view = self._logs(raw)
        elif method in {"get_traces", "get_dependency_traces"}:
            view = self._traces(method, raw)
        elif method == "get_cluster_resource_context":
            view = self._cluster_resource_context(raw)
        else:
            view = self._base(method, raw)

        view["tool"] = method
        view["call_id"] = raw.get("call_id", "")
        view["timestamp"] = raw.get("timestamp", "")
        view["service"] = raw.get("service", "")
        view["raw_refs"] = self._raw_refs(method, raw)
        if raw.get("error"):
            view["status"] = "error"
            view["observability_gaps"].append(str(raw.get("error")))
        return view

    def _cluster_resource_context(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        view = self._base("get_cluster_resource_context", raw)
        service = str(raw.get("service", "")).strip() or "service"
        workloads = list(raw.get("active_non_app_workloads", []) or [])
        pressure = dict(raw.get("resource_pressure", {}) or {})
        resource = str(pressure.get("resource", "unknown") or "unknown").strip().lower()
        if workloads:
            phases = Counter(str(item.get("phase", "unknown") or "unknown") for item in workloads)
            nodes = sorted({str(item.get("node", "")).strip() for item in workloads if str(item.get("node", "")).strip()})
            view["key_facts"].append(
                {
                    "active_non_app_workloads": {
                        "count": len(workloads),
                        "phases": dict(phases),
                        "nodes": nodes[:5],
                    }
                }
            )
            view["anomalies"].append(
                {
                    "type": "external_resource_pressure",
                    "resource": resource if resource in {"cpu", "memory"} else "unknown",
                    "scope": "node_or_namespace",
                }
            )
        else:
            view["negative_evidence"].append("No active non-application pressure workload was included in this evidence context.")

        if raw.get("app_local_saturation_absent"):
            view["negative_evidence"].append(
                f"{service} app-local CPU, memory, and throttling metrics do not show limit saturation."
            )
        for item in raw.get("negative_evidence", []) or []:
            text = str(item).strip()
            if text:
                view["negative_evidence"].append(text)

        if view["anomalies"]:
            view["status"] = "anomalous"
            view["summary"] = "Non-application workload activity is present during the incident window."
        else:
            view["summary"] = "No non-application resource pressure context was returned."
        return view

    def _base(self, tool: str, raw: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "ok",
            "summary": f"{tool} returned evidence for {raw.get('service', 'unknown service')}",
            "key_facts": [],
            "anomalies": [],
            "negative_evidence": [],
            "observability_gaps": [],
        }

    def _k8s_state(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        view = self._base("get_k8s_state", raw)
        service = str(raw.get("service", "")).strip() or "service"
        desired = _to_int(raw.get("desired_replicas"))
        available = _to_int(raw.get("available_replicas"))
        restarts = _to_int(raw.get("restart_count"))
        rollout = bool(raw.get("rollout_progressing", False))
        pod_phases = list(raw.get("pod_phases", []) or [])
        service_summary = dict(raw.get("service_config_summary", {}) or {})
        service_config = dict(raw.get("service_config", {}) or {})
        deployment_config = dict(raw.get("deployment_config", {}) or {})

        view["key_facts"].append(f"Replicas available/desired: {available}/{desired}.")
        view["key_facts"].append(f"Rollout progressing: {rollout}; total restart count: {restarts}.")
        if pod_phases:
            phase_counts = Counter(str(p.get("phase", "unknown")) for p in pod_phases)
            ready_count = sum(1 for p in pod_phases if bool(p.get("ready", False)))
            view["key_facts"].append(f"Pods ready/total: {ready_count}/{len(pod_phases)}; phases: {dict(phase_counts)}.")
            non_ready = [
                {
                    "pod": p.get("pod_name", ""),
                    "phase": p.get("phase", ""),
                    "ready": bool(p.get("ready", False)),
                    "restarts": _to_int(p.get("restart_count")),
                }
                for p in pod_phases
                if not bool(p.get("ready", False)) or str(p.get("phase", "")) != "Running" or _to_int(p.get("restart_count")) > 0
            ]
            if non_ready:
                view["anomalies"].append({"type": "pod_not_fully_healthy", "pods": non_ready[:5]})
            else:
                view["negative_evidence"].append("All listed pods are Running, ready, and have no restarts.")

        if desired > available:
            view["anomalies"].append({"type": "availability_gap", "available": available, "desired": desired})
        else:
            view["negative_evidence"].append("No replica availability gap is visible.")
        if rollout:
            view["anomalies"].append({"type": "rollout_in_progress_or_stalled", "rollout_progressing": True})

        if service_summary or service_config:
            self._add_service_config_facts(view, service_summary, service_config)
        if deployment_config:
            self._add_deployment_config_facts(view, deployment_config)
        events = list(raw.get("recent_events", []) or [])
        self._add_lifecycle_facts(view, desired, available, pod_phases, events, rollout)
        self._add_recent_event_facts(view, events)

        if view["anomalies"]:
            view["status"] = "anomalous"
            view["summary"] = f"Kubernetes evidence for {service} has {len(view['anomalies'])} anomaly group(s)."
        else:
            view["summary"] = f"Kubernetes workload and Service evidence for {service} shows no obvious anomaly."
        return view

    def _add_service_config_facts(
        self,
        view: Dict[str, Any],
        service_summary: Dict[str, Any],
        service_config: Dict[str, Any],
    ) -> None:
        selector = service_summary.get("selector", service_config.get("selector", {}))
        ports = service_summary.get("service_ports", service_config.get("ports", []))
        container_ports = service_summary.get("container_ports", _container_ports_from_service_config(service_config))
        endpoint_counts = service_summary.get("endpoint_counts", {})
        selected_count = _to_int(service_summary.get("selected_pod_count", len(service_config.get("selected_pods", []) or [])))
        deployment_count = _to_int(service_summary.get("deployment_pod_count", len(service_config.get("deployment_pods", []) or [])))

        view["key_facts"].append(f"Service selector: {_short_json(selector)}.")
        view["key_facts"].append(f"Service-selected pods/deployment pods: {selected_count}/{deployment_count}.")
        view["key_facts"].append(f"Service ports/targetPorts: {_ports_summary(ports)}.")
        view["key_facts"].append(f"Selected pod container ports: {_container_ports_summary(container_ports)}.")
        if endpoint_counts:
            ready = endpoint_counts.get("effective_ready", endpoint_counts.get("ready", endpoint_counts.get("ready_addresses", 0)))
            not_ready = endpoint_counts.get(
                "effective_not_ready",
                endpoint_counts.get("not_ready", endpoint_counts.get("not_ready_addresses", 0)),
            )
            view["key_facts"].append(f"Effective endpoints ready/not-ready: {_to_int(ready)}/{_to_int(not_ready)}.")

        alignment = dict(service_summary.get("service_port_alignment", {}) or {})
        if alignment:
            if bool(alignment.get("aligned", False)):
                view["negative_evidence"].append("Service targetPort values align with exposed selected-pod container ports.")
            else:
                mismatches = list(alignment.get("mismatches", []) or [])
                view["anomalies"].append(
                    {
                        "type": "port_inconsistency",
                        "scope": "service",
                        "evidence_refs": ["service_ports", "selected_pod_container_ports"],
                        "count": len(mismatches),
                    }
                )
        if selected_count == 0 and deployment_count > 0:
            view["anomalies"].append({"type": "service_selector_matches_no_deployment_pods", "selector": selector})

        generic_service_signals = 0
        for anomaly in service_summary.get("anomalies", []) or []:
            text = str(anomaly).strip()
            if text:
                generic_service_signals += 1
        if generic_service_signals:
            view["anomalies"].append({"type": "service_config_signal", "scope": "service", "count": generic_service_signals})
        takeaway = str(service_summary.get("takeaway", "")).strip()
        if takeaway:
            view["key_facts"].append(takeaway)

    def _add_deployment_config_facts(self, view: Dict[str, Any], deployment_config: Dict[str, Any]) -> None:
        containers = list(deployment_config.get("containers", []) or [])
        if containers:
            details = []
            for container in containers[:4]:
                details.append(
                    {
                        "name": container.get("name", ""),
                        "image": container.get("image", ""),
                        "ports": container.get("ports", []),
                        "resources": container.get("resources", {}),
                        "readinessProbe": bool(container.get("readinessProbe")),
                        "livenessProbe": bool(container.get("livenessProbe")),
                    }
                )
            view["key_facts"].append(f"Deployment containers: {_short_json(details)}.")

        env = list(deployment_config.get("env", []) or [])
        interesting_env = [
            {
                "container": item.get("container", ""),
                "name": item.get("name", ""),
                "value": item.get("value", ""),
                "value_from": item.get("value_from", {}),
                "value_redacted": bool(item.get("value_redacted", False)),
            }
            for item in env
            if any(token in str(item.get("name", "")).upper() for token in ("SERVICE", "ADDR", "HOST", "PORT"))
        ]
        if interesting_env:
            view["key_facts"].append(f"Relevant deployment env/config values: {_short_json(interesting_env[:12])}.")
            addresses = _dependency_addresses_from_env(interesting_env)
            if addresses:
                view["key_facts"].append({"configured_dependency_addresses": addresses[:12]})
                unusual = [item for item in addresses if item.get("port") in {0, 1} or _to_int(item.get("port")) > 65535]
                if unusual:
                    view["anomalies"].append(
                        {
                            "type": "port_inconsistency",
                            "scope": "dependency_config",
                            "evidence_refs": ["configured_dependency_addresses"],
                            "count": len(unusual),
                        }
                    )

    def _add_lifecycle_facts(
        self,
        view: Dict[str, Any],
        desired: int,
        available: int,
        pod_phases: List[Dict[str, Any]],
        events: List[Dict[str, Any]],
        rollout: bool,
    ) -> None:
        if desired == 0:
            view["anomalies"].append(
                {
                    "type": "desired_replicas_zero",
                    "available": available,
                    "listed_pods": len(pod_phases),
                    "interpretation": "Deployment desired replica count is zero in Kubernetes state.",
                }
            )
            view["negative_evidence"].append("No pod crash is needed to explain zero availability when desired replicas are zero.")

        event_text = _events_text(events)
        if "scaled down" in event_text and re.search(r"\bto 0\b", event_text):
            view["anomalies"].append({"type": "deployment_scaled_down_to_zero_event"})

        delete_events = _matching_events(events, ("successfuldelete", "deleted pod"))
        create_events = _matching_events(events, ("successfulcreate", "created pod", "scheduled"))
        killing_events = _matching_events(events, ("killing", "stopping container"))
        image_pull_events = _matching_events(events, ("imagepull", "errimagepull", "pulling image", "failed to pull"))
        probe_events = _matching_events(events, ("readiness probe failed", "liveness probe failed"))

        if delete_events or (killing_events and create_events):
            view["anomalies"].append(
                {
                    "type": "pod_lifecycle_replacement_events",
                    "deleted_or_killed": len(delete_events) + len(killing_events),
                    "created_or_scheduled": len(create_events),
                    "rollout_progressing": rollout,
                    "events": (delete_events + killing_events + create_events)[:5],
                }
            )
            if not image_pull_events:
                view["negative_evidence"].append("Pod replacement events were returned without image-pull failure events.")
            if not probe_events:
                view["negative_evidence"].append("Pod replacement events were returned without probe-failure warning events.")
        elif rollout and not image_pull_events and not probe_events:
            view["negative_evidence"].append("Rollout is marked progressing, but no image-pull or probe-failure event was returned.")

    def _add_recent_event_facts(self, view: Dict[str, Any], events: List[Dict[str, Any]]) -> None:
        if not events:
            view["negative_evidence"].append("No recent Kubernetes events were returned.")
            return
        meaningful = []
        for event in events:
            reason = str(event.get("reason", ""))
            message = str(event.get("message", ""))
            event_type = str(event.get("type", ""))
            text = f"{reason} {message}".lower()
            if event_type.lower() == "warning" or any(token in text for token in _EVENT_SIGNAL_TOKENS):
                meaningful.append(
                    {
                        "reason": reason,
                        "object": event.get("object", ""),
                        "type": event_type,
                        "message": _truncate(message, 180),
                        "stale": bool(event.get("stale", False)),
                    }
                )
        if meaningful:
            view["anomalies"].append({"type": "meaningful_kubernetes_events", "events": meaningful[:6]})
        else:
            view["negative_evidence"].append("Returned Kubernetes events contain no warning/failure signals.")

    def _logs(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        view = self._base("get_logs", raw)
        service = str(raw.get("service", "")).strip() or "service"
        lines = _log_lines(raw)
        if not lines:
            view["summary"] = f"Logs for {service} returned no signal lines."
            view["negative_evidence"].append("No error or signal log lines were returned.")
            return view

        groups: Counter[str] = Counter(_classify_log_line(line) for line in lines)
        view["key_facts"].append(f"Log signal groups: {dict(groups)}.")
        snippets = []
        seen_classes = set()
        for line in lines:
            klass = _classify_log_line(line)
            if klass in seen_classes and len(snippets) >= 4:
                continue
            seen_classes.add(klass)
            snippets.append({"signal_class": klass, "snippet": _truncate(line, 240)})
            if len(snippets) >= 6:
                break
        view["key_facts"].append({"representative_snippets": snippets})
        if any(name != "informational" for name in groups):
            view["status"] = "anomalous"
            view["anomalies"].append({"type": "log_signal_patterns", "groups": dict(groups)})
            view["summary"] = f"Logs for {service} contain {sum(groups.values())} signal line(s) across {len(groups)} group(s)."
        else:
            view["summary"] = f"Logs for {service} contain only informational sampled lines."
            view["negative_evidence"].append("No error, timeout, OOM, throttling, or connection-failure log pattern was grouped.")
        return view

    def _metrics(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        view = self._base("get_metrics", raw)
        service = str(raw.get("service", "")).strip() or "service"
        metrics = dict(raw.get("metrics", {}) or {})
        if not metrics:
            view["summary"] = f"Metrics for {service} were unavailable."
            view["observability_gaps"].append("No metrics payload was returned.")
            return view

        error_rate = _metric(metrics, "error_rate", "error_rate_pct", pct_to_ratio=True)
        p95 = _metric(metrics, "p95_latency_ms", "latency_p95_ms")
        p99 = _metric(metrics, "p99_latency_ms", "latency_p99_ms")
        rps = _metric(metrics, "request_rps")
        cpu_limit = _metric(metrics, "cpu_utilization_pct_of_limit", "cpu_limit_pct")
        cpu_request = _metric(metrics, "cpu_utilization_pct_of_request")
        cpu_throttle = _metric(metrics, "cpu_throttling_ratio", "cpu_throttle_pct", pct_to_ratio=True)
        mem_limit = _metric(metrics, "memory_utilization_pct_of_limit", "memory_limit_pct")
        mem_request = _metric(metrics, "memory_utilization_pct_of_request")

        view["key_facts"].append(
            f"Traffic health: rps={rps:.3g}, error_rate={error_rate * 100.0:.3g}%, p95={p95:.3g}ms, p99={p99:.3g}ms."
        )
        view["key_facts"].append(
            f"CPU: limit_util={cpu_limit:.3g}%, request_util={cpu_request:.3g}%, throttling={cpu_throttle * 100.0:.3g}%."
        )
        view["key_facts"].append(f"Memory: limit_util={mem_limit:.3g}%, request_util={mem_request:.3g}%.")
        headroom = {
            "cpu_cores_to_limit": metrics.get("cpu_headroom_cores_to_limit"),
            "memory_bytes_to_limit": metrics.get("memory_headroom_bytes_to_limit"),
        }
        if any(value is not None for value in headroom.values()):
            view["key_facts"].append({"resource_headroom": headroom})

        if error_rate > 0.01:
            view["anomalies"].append({"type": "error_rate_elevated", "error_rate": error_rate})
        if p99 >= 250.0:
            view["anomalies"].append({"type": "latency_elevated", "p99_latency_ms": p99})
        if cpu_throttle >= 0.10:
            view["anomalies"].append({"type": "cpu_throttling_elevated", "cpu_throttling_ratio": cpu_throttle})
        if cpu_limit >= 80.0:
            view["anomalies"].append({"type": "cpu_limit_pressure", "cpu_limit_pct": cpu_limit})
        if mem_limit >= 80.0:
            view["anomalies"].append({"type": "memory_limit_pressure", "memory_limit_pct": mem_limit})

        self._add_resource_pressure_profile(view, raw, metrics, error_rate, p99, cpu_limit, cpu_throttle, mem_limit)

        for gap in metrics.get("resource_metric_gaps", []) or []:
            view["observability_gaps"].append(str(gap))
        for gap in metrics.get("application_metric_gaps", []) or []:
            view["observability_gaps"].append(str(gap))
        if not bool(metrics.get("resource_metrics_available", True)):
            view["observability_gaps"].append("Resource metrics unavailable.")
        if not bool(metrics.get("application_metrics_available", True)):
            view["observability_gaps"].append("Application metrics unavailable.")

        if view["anomalies"]:
            view["status"] = "anomalous"
            view["summary"] = f"Metrics for {service} show {len(view['anomalies'])} health/resource anomaly group(s)."
        else:
            view["summary"] = f"Metrics for {service} show low error rate, bounded latency, and no resource saturation signal."
            view["negative_evidence"].append("No elevated error rate, latency breach, throttling, CPU pressure, or memory pressure in metrics.")
        return view

    def _add_resource_pressure_profile(
        self,
        view: Dict[str, Any],
        raw: Dict[str, Any],
        metrics: Dict[str, Any],
        error_rate: float,
        p99: float,
        cpu_limit: float,
        cpu_throttle: float,
        mem_limit: float,
    ) -> None:
        active_stress = _active_stress_workloads(raw)
        if active_stress:
            view["anomalies"].append({"type": "active_external_stress_workloads", "workloads": active_stress[:5]})
            view["key_facts"].append("Active non-application stress workload evidence is present in the raw metrics context.")

        app_saturated = cpu_limit >= 80.0 or mem_limit >= 80.0 or cpu_throttle >= 0.10
        user_visible_degradation = p99 >= 250.0 or error_rate > 0.01
        if user_visible_degradation and not app_saturated:
            view["anomalies"].append(
                {
                    "type": "latency_or_errors_without_app_resource_saturation",
                    "p99_latency_ms": p99,
                    "error_rate": error_rate,
                    "cpu_limit_pct": cpu_limit,
                    "cpu_throttling_ratio": cpu_throttle,
                    "memory_limit_pct": mem_limit,
                }
            )
            view["negative_evidence"].append(
                "App-local CPU, memory, and throttling metrics do not show limit saturation; resource symptoms may be external/node-level or dependency-driven."
            )
        elif app_saturated:
            view["key_facts"].append("App-local resource saturation evidence is present.")

    def _traces(self, tool: str, raw: Dict[str, Any]) -> Dict[str, Any]:
        view = self._base(tool, raw)
        service = str(raw.get("service", "")).strip() or "service"
        trace_count = _to_int(raw.get("trace_count", raw.get("focus_trace_count", 0)))
        entry = str(raw.get("entry_service", raw.get("entry_point", ""))).strip()
        if entry:
            view["key_facts"].append(f"Entry service: {entry}.")
        view["key_facts"].append(f"Trace count: {trace_count}.")

        candidates = list(raw.get("downstream_candidates", []) or [])
        if candidates:
            top = candidates[0]
            view["key_facts"].append(
                f"Top downstream candidate: {top.get('service', '')} avg_duration={_to_float(top.get('avg_duration_ms')):.3g}ms pct={_to_float(top.get('avg_pct_of_total')):.3g}."
            )
            slow = [
                {
                    "service": item.get("service", ""),
                    "avg_duration_ms": _to_float(item.get("avg_duration_ms")),
                    "avg_pct_of_total": _to_float(item.get("avg_pct_of_total")),
                    "count": _to_int(item.get("count")),
                }
                for item in candidates
                if _to_float(item.get("avg_pct_of_total")) >= 0.25 or _to_float(item.get("avg_duration_ms")) >= 100.0
            ]
            if slow:
                view["anomalies"].append({"type": "slow_or_dominant_downstream_edges", "edges": slow[:5]})

        call_chain = list(raw.get("call_chain", []) or [])
        error_spans = list(raw.get("error_spans", []) or [])
        bottleneck = str(raw.get("bottleneck_service", raw.get("bottleneck", ""))).strip()
        bottleneck_pct = _to_float(raw.get("bottleneck_pct_of_total"))
        if bottleneck:
            view["key_facts"].append(f"Bottleneck service: {bottleneck} ({bottleneck_pct:.3g} of total when available).")
            if bottleneck_pct >= 0.35:
                view["anomalies"].append({"type": "trace_bottleneck", "service": bottleneck, "pct_of_total": bottleneck_pct})
        if call_chain:
            compact_chain = [
                {
                    "service": span.get("service", ""),
                    "operation": _truncate(str(span.get("operation", "")), 80),
                    "duration_ms": _to_float(span.get("duration_ms")),
                    "error": bool(span.get("error", False)) or str(span.get("status", "")).upper() == "ERROR",
                    "peer_service": span.get("peer_service", ""),
                }
                for span in call_chain[:8]
            ]
            view["key_facts"].append({"critical_path_sample": compact_chain})
        if error_spans:
            view["anomalies"].append({"type": "error_spans", "spans": error_spans[:5]})
        else:
            view["negative_evidence"].append("No error spans were returned.")

        quality = str(raw.get("trace_quality", "")).strip()
        if raw.get("observability_error") or raw.get("error") or quality in {"unavailable", "missing", "weak"}:
            view["observability_gaps"].append(f"Trace quality is {quality or 'unavailable'}.")
        if trace_count <= 0:
            view["observability_gaps"].append("No traces returned in the lookback window.")

        if view["anomalies"]:
            view["status"] = "anomalous"
            view["summary"] = f"Trace evidence for {service} has {len(view['anomalies'])} slow/error signal group(s)."
        else:
            view["summary"] = f"Trace evidence for {service} has no returned error span or dominant downstream bottleneck."
        return view

    def _raw_refs(self, tool: str, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        refs = [{"tool": tool, "call_id": raw.get("call_id", ""), "timestamp": raw.get("timestamp", "")}]
        for ref in raw.get("raw_refs", []) or []:
            if isinstance(ref, dict):
                refs.append(dict(ref))
        if "raw_output" in raw:
            nested = raw.get("raw_output") or {}
            refs.append(
                {
                    "tool": tool,
                    "call_id": nested.get("call_id", raw.get("call_id", "")) if isinstance(nested, dict) else raw.get("call_id", ""),
                    "timestamp": nested.get("timestamp", raw.get("timestamp", "")) if isinstance(nested, dict) else raw.get("timestamp", ""),
                    "artifact": "packaged_raw_payload",
                }
            )
        return refs


def compact_evidence(tool: str, output: Dict[str, Any]) -> Dict[str, Any]:
    return EvidenceDistiller().distill(tool, output)


def add_cross_record_evidence(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Add deterministic comparisons that require more than one compact evidence view."""

    rows = deepcopy(records)
    service_ports: Dict[str, set[int]] = {}
    for row in rows:
        evidence = dict(row.get("evidence", {}) or {})
        service = _normalize_service_name(evidence.get("service") or (row.get("inputs", {}) or {}).get("service"))
        if not service:
            continue
        ports = _observed_ports_from_compact_evidence(evidence)
        if ports:
            service_ports.setdefault(service, set()).update(ports)

    for row in rows:
        evidence = row.get("evidence", {}) or {}
        if not isinstance(evidence, dict):
            continue
        mismatches = []
        for address in _dependency_addresses_from_compact_evidence(evidence):
            host = _normalize_service_name(address.get("host"))
            port = _to_int(address.get("port"))
            observed = service_ports.get(host, set())
            if observed and port not in observed:
                mismatch = dict(address)
                mismatch["observed_ports_for_host"] = sorted(observed)
                mismatches.append(mismatch)
        if mismatches:
            evidence.setdefault("anomalies", []).append(
                {
                    "type": "port_inconsistency",
                    "scope": "dependency",
                    "evidence_refs": ["configured_dependency_addresses", "observed_service_ports"],
                    "count": len(mismatches),
                }
            )
            observed_by_host: Dict[str, List[int]] = {}
            for item in mismatches[:6]:
                host = str(item.get("host", "")).strip()
                if host:
                    observed_by_host[host] = list(item.get("observed_ports_for_host", []) or [])
            evidence.setdefault("key_facts", []).append(
                {"observed_service_ports": observed_by_host}
            )
            evidence.setdefault("negative_evidence", []).append(
                "Configured dependency addresses and observed downstream Service/container ports both appear in evidence."
            )
    return rows


def select_compact_evidence_records(records: List[Dict[str, Any]], *, max_records: int) -> List[Dict[str, Any]]:
    """Select a compact, dependency-aware evidence subset while preserving replay determinism."""

    if max_records <= 0:
        return []
    rows = list(records)
    if len(rows) <= max_records:
        return add_cross_record_evidence(rows)

    primary_service = ""
    for row in rows:
        primary_service = _row_service(row)
        if primary_service:
            break

    selected: List[Dict[str, Any]] = []

    def add(row: Dict[str, Any]) -> None:
        if row not in selected and len(selected) < max_records:
            selected.append(row)

    primary_rows = [row for row in rows if _row_service(row) == primary_service]
    for tool in (
        "get_k8s_state",
        "get_metrics",
        "get_cluster_resource_context",
        "get_logs",
        "get_dependency_traces",
        "get_traces",
    ):
        for row in primary_rows:
            if row.get("tool") == tool:
                add(row)

    primary_text = " ".join(
        str(row.get("evidence", ""))
        for row in primary_rows
        if row.get("tool") in {"get_logs", "get_traces", "get_dependency_traces"}
    ).lower()
    dependency_hosts = _dependency_hosts_from_rows(primary_rows)
    dependency_hosts.sort(
        key=lambda host: (
            0 if host in primary_text else 1,
            _dependency_port_rank(primary_rows, host),
            host,
        )
    )
    for host in dependency_hosts:
        for row in rows:
            if row.get("tool") == "get_k8s_state" and _row_service(row) == host:
                add(row)
                break

    for row in rows:
        add(row)
        if len(selected) >= max_records:
            break

    return add_cross_record_evidence(selected)


def _log_lines(raw: Dict[str, Any]) -> List[str]:
    if raw.get("lines"):
        return [str((item or {}).get("msg", item)) if isinstance(item, dict) else str(item) for item in raw.get("lines", [])]
    lines: List[str] = []
    for key in ("signal_lines", "error_lines", "recent_lines"):
        lines.extend(str(item) for item in raw.get(key, []) or [])
    for pod in raw.get("pods", []) or []:
        for key in ("signal_lines", "error_lines", "recent_lines"):
            lines.extend(str(item) for item in (pod or {}).get(key, []) or [])
    return lines


def _classify_log_line(line: str) -> str:
    text = line.lower()
    if "oom" in text or "out of memory" in text or "killed" in text:
        return "oom_or_killed"
    if "thrott" in text:
        return "cpu_throttling"
    if "deadline exceeded" in text or "timeout" in text or "timed out" in text:
        return "timeout"
    if "connection refused" in text or "unavailable" in text or "no such host" in text or "dns" in text:
        return "dependency_connection_failure"
    if "imagepull" in text or "errimagepull" in text:
        return "image_pull"
    if "error" in text or "exception" in text or "fatal" in text:
        return "application_error"
    return "informational"


def _metric(metrics: Dict[str, Any], primary: str, fallback: str = "", *, pct_to_ratio: bool = False) -> float:
    value = metrics.get(primary)
    if value is None and fallback:
        value = metrics.get(fallback)
        if pct_to_ratio and value is not None:
            return _to_float(value) / 100.0
    return _to_float(value)


def _to_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _short_json(value: Any, limit: int = 900) -> str:
    text = repr(value)
    return _truncate(text, limit)


def _truncate(value: str, limit: int) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def _ports_summary(ports: Iterable[Dict[str, Any]]) -> str:
    rows = []
    for port in ports or []:
        rows.append(f"port={port.get('port')} targetPort={port.get('targetPort')} name={port.get('name', '')}")
    return "; ".join(rows) if rows else "none returned"


def _container_ports_summary(ports: Iterable[Dict[str, Any]]) -> str:
    rows = []
    for port in ports or []:
        rows.append(f"container={port.get('container', '')} port={port.get('containerPort')} name={port.get('name', '')}")
    return "; ".join(rows) if rows else "none returned"


def _container_ports_from_service_config(service_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    ports: List[Dict[str, Any]] = []
    for pod in list(service_config.get("selected_pods", []) or []) + list(service_config.get("deployment_pods", []) or []):
        for port in (pod or {}).get("container_ports", []) or []:
            if port not in ports:
                ports.append(port)
    return ports


def _events_text(events: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for event in events:
        parts.extend([str(event.get("reason", "")), str(event.get("message", "")), str(event.get("object", ""))])
    return " ".join(parts).lower()


def _matching_events(events: List[Dict[str, Any]], tokens: Iterable[str]) -> List[Dict[str, Any]]:
    lowered = [str(token).lower() for token in tokens]
    matches = []
    for event in events:
        text = f"{event.get('reason', '')} {event.get('message', '')}".lower()
        if any(token in text for token in lowered):
            matches.append(
                {
                    "reason": event.get("reason", ""),
                    "object": event.get("object", ""),
                    "type": event.get("type", ""),
                    "message": _truncate(str(event.get("message", "")), 160),
                    "stale": bool(event.get("stale", False)),
                }
            )
    return matches


def _dependency_addresses_from_env(env: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    addresses = []
    for item in env:
        name = str(item.get("name", ""))
        value = str(item.get("value", ""))
        if not value or bool(item.get("value_redacted", False)):
            continue
        parsed = _parse_host_port(value)
        if not parsed:
            continue
        host, port = parsed
        role = name
        for suffix in ("_SERVICE_ADDR", "_ADDR", "_HOST", "_PORT"):
            if role.endswith(suffix):
                role = role[: -len(suffix)]
                break
        addresses.append(
            {
                "env": name,
                "dependency_hint": role.lower(),
                "host": host,
                "port": port,
                "container": item.get("container", ""),
            }
        )
    return addresses


def _parse_host_port(value: str) -> tuple[str, int] | None:
    text = value.strip()
    if not text or "/" in text or "=" in text:
        return None
    if ":" not in text:
        return None
    host, port_text = text.rsplit(":", 1)
    if not host or not port_text.isdigit():
        return None
    return host, _to_int(port_text)


def _active_stress_workloads(value: Any) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            active = node.get("active_stress_jobs") or node.get("active_stress_workloads")
            if isinstance(active, list):
                for item in active:
                    if isinstance(item, dict):
                        found.append(
                            {
                                "pod": item.get("pod", ""),
                                "job": item.get("job", item.get("name", "")),
                                "phase": item.get("phase", ""),
                                "node": item.get("node", ""),
                            }
                        )
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
    unique: List[Dict[str, Any]] = []
    seen = set()
    for item in found:
        key = tuple(sorted((str(k), str(v)) for k, v in item.items()))
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _dependency_addresses_from_compact_evidence(evidence: Dict[str, Any]) -> List[Dict[str, Any]]:
    addresses: List[Dict[str, Any]] = []
    for fact in evidence.get("key_facts", []) or []:
        if not isinstance(fact, dict):
            continue
        for key in ("configured_dependency_addresses", "dependency_address_config"):
            values = fact.get(key)
            if isinstance(values, list):
                addresses.extend(item for item in values if isinstance(item, dict))
    return addresses


def _observed_ports_from_compact_evidence(evidence: Dict[str, Any]) -> set[int]:
    ports: set[int] = set()
    for fact in evidence.get("key_facts", []) or []:
        if not isinstance(fact, str):
            continue
        if fact.startswith("Service ports/targetPorts:") or fact.startswith("Selected pod container ports:"):
            for value in re.findall(r"(?:port|targetPort)=(\d+)", fact):
                ports.add(_to_int(value))
    return {port for port in ports if port > 0}


def _normalize_service_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    if "." in text:
        text = text.split(".", 1)[0]
    return text


def _row_service(row: Dict[str, Any]) -> str:
    evidence = row.get("evidence", {}) if isinstance(row.get("evidence", {}), dict) else {}
    inputs = row.get("inputs", {}) if isinstance(row.get("inputs", {}), dict) else {}
    return _normalize_service_name(evidence.get("service") or inputs.get("service"))


def _dependency_hosts_from_rows(rows: List[Dict[str, Any]]) -> List[str]:
    hosts = []
    for row in rows:
        evidence = row.get("evidence", {}) if isinstance(row.get("evidence", {}), dict) else {}
        for address in _dependency_addresses_from_compact_evidence(evidence):
            host = _normalize_service_name(address.get("host"))
            if host and host not in hosts:
                hosts.append(host)
    return hosts


def _dependency_port_rank(rows: List[Dict[str, Any]], host: str) -> int:
    for row in rows:
        evidence = row.get("evidence", {}) if isinstance(row.get("evidence", {}), dict) else {}
        for address in _dependency_addresses_from_compact_evidence(evidence):
            if _normalize_service_name(address.get("host")) == host:
                port = _to_int(address.get("port"))
                if port in {0, 1} or port > 65535:
                    return 0
    return 1


_EVENT_SIGNAL_TOKENS = (
    "fail",
    "backoff",
    "unhealthy",
    "killing",
    "pull",
    "oom",
    "created",
    "scheduled",
    "deleted",
)
