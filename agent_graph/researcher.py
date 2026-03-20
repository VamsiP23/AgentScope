from __future__ import annotations

from typing import List

from agent_graph.knowledge.topology import downstream_dependencies, topology_summary, upstream_surfaces
from agent_graph.schemas import EvidenceItem, Hypothesis
from agent_graph.tools.jaeger import JaegerTools
from agent_graph.tools.kubernetes import KubernetesTools
from agent_graph.tools.prometheus import PrometheusTools
from detectors.schemas import DetectionConfig


class Researcher:
    def __init__(self, config: DetectionConfig, prom: PrometheusTools, k8s: KubernetesTools, jaeger: JaegerTools) -> None:
        self.config = config
        self.prom = prom
        self.k8s = k8s
        self.jaeger = jaeger

    def run(self, hypotheses: List[Hypothesis]) -> List[EvidenceItem]:
        evidence: List[EvidenceItem] = []
        window = self.config.window
        target = self.config.target_deployment
        primary_service = (hypotheses[0].suspected_service if hypotheses else "") or target

        if primary_service:
            evidence.append(
                EvidenceItem(
                    source="knowledge",
                    name="service_topology",
                    summary=topology_summary(primary_service),
                    supports=[],
                    details={
                        "service": primary_service,
                        "downstream_dependencies": downstream_dependencies(primary_service),
                        "upstream_surfaces": upstream_surfaces(primary_service),
                    },
                )
            )

        dep = self.k8s.deployment_health(self.config.namespace, target) if target else {}
        if dep:
            evidence.append(
                EvidenceItem(
                    source="kubernetes",
                    name="deployment_health",
                    summary=f"deployment {target} available={dep.get('available', 0)} desired={dep.get('desired', 0)}",
                    supports=["deployment_unavailable"] if not dep.get("healthy", True) else [],
                    contradicts=["deployment_unavailable"] if dep.get("healthy", True) else [],
                    details=dep,
                )
            )

        top_errors = self.prom.top_error_services(window, limit=5)
        evidence.append(
            EvidenceItem(
                source="prometheus",
                name="top_error_services",
                summary=(
                    f"top error service: {top_errors[0]['service_name']} at {top_errors[0]['error_rps']:.3f} rps"
                    if top_errors
                    else "no error services"
                ),
                supports=["frontend_symptom_from_downstream_failure"] if top_errors else [],
                details={"top_error_services": top_errors},
            )
        )

        global_errors = self.prom.global_error_ratio(window)
        evidence.append(
            EvidenceItem(
                source="prometheus",
                name="global_error_ratio",
                summary=f"error_ratio={global_errors['error_ratio']:.3f} total_rps={global_errors['total_rps']:.3f}",
                supports=["performance_degradation"] if global_errors["error_ratio"] >= self.config.error_ratio_threshold else [],
                details=global_errors,
            )
        )

        trace_service = primary_service or "frontend"
        trace_summary = self.jaeger.latest_application_trace(trace_service)
        trace_supports = []
        if trace_summary.get("error_spans"):
            trace_supports.append("frontend_symptom_from_downstream_failure")
            trace_supports.append("dependency_outage")
        evidence.append(
            EvidenceItem(
                source="jaeger",
                name="latest_trace",
                summary=trace_summary.get("summary", "no trace summary"),
                supports=trace_supports,
                details=trace_summary,
            )
        )

        for dependency in downstream_dependencies(primary_service):
            dep_trace = self.jaeger.latest_application_trace(dependency)
            dep_supports = ["dependency_outage"] if dep_trace.get("error_spans") else []
            evidence.append(
                EvidenceItem(
                    source="jaeger",
                    name=f"dependency_trace:{dependency}",
                    summary=dep_trace.get("summary", f"no trace summary for {dependency}"),
                    supports=dep_supports,
                    details=dep_trace,
                )
            )

        restarts = self.k8s.top_pod_restarts(self.config.namespace, limit=5)
        evidence.append(
            EvidenceItem(
                source="kubernetes",
                name="restart_history",
                summary=f"pods with restart history={len(restarts)}",
                supports=[],
                details={"top_pod_restarts": restarts},
            )
        )

        events = self.k8s.recent_events(self.config.namespace, limit=10)
        event_supports = []
        if any("Back-off" in item.get("reason", "") or "Unhealthy" in item.get("reason", "") for item in events):
            event_supports.append("deployment_unavailable")
        evidence.append(
            EvidenceItem(
                source="kubernetes",
                name="recent_events",
                summary=f"recent events collected={len(events)}",
                supports=event_supports,
                details={"events": events},
            )
        )
        return evidence

    def select_supported_hypothesis(self, hypotheses: List[Hypothesis], evidence: List[EvidenceItem]) -> Hypothesis:
        scores = {hyp.id: hyp.confidence for hyp in hypotheses}
        by_id = {hyp.id: hyp for hyp in hypotheses}
        for item in evidence:
            for hyp_id in item.supports:
                scores[hyp_id] = scores.get(hyp_id, 0.0) + 0.15
            for hyp_id in item.contradicts:
                scores[hyp_id] = scores.get(hyp_id, 0.0) - 0.25
        best_id = max(scores, key=scores.get)
        best = by_id[best_id]
        best.confidence = max(0.0, min(0.99, scores[best_id]))
        return best
