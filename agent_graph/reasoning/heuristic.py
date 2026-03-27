from __future__ import annotations

from typing import Any, Dict, List

from agent_graph.schemas import Hypothesis


class HeuristicHypothesizer:
    def rank(self, detection: Dict[str, Any], target_deployment: str) -> List[Hypothesis]:
        findings = {item["name"]: item for item in detection.get("findings", [])}
        hypotheses: List[Hypothesis] = []

        availability = findings.get("deployment_availability", {})
        service_error = findings.get("service_error_rate", {})
        error_ratio = findings.get("error_ratio", {})
        service_latency = findings.get("service_latency", {})

        if availability.get("triggered"):
            hypotheses.append(
                Hypothesis(
                    id="deployment_unavailable",
                    title="Target deployment unavailable",
                    suspected_service=availability.get("service") or target_deployment,
                    category="availability",
                    confidence=0.92,
                    rationale=availability.get("reason", "target deployment unhealthy"),
                    validation_plan=[
                        "Confirm deployment desired vs available replicas",
                        "Check recent frontend error concentration",
                        "Inspect latest trace for downstream failure propagation",
                    ],
                )
            )

        if service_error.get("triggered"):
            top_service = service_error.get("service", "frontend")
            hypotheses.append(
                Hypothesis(
                    id="frontend_symptom_from_downstream_failure",
                    title="Frontend errors likely caused by downstream dependency",
                    suspected_service=target_deployment or top_service,
                    category="dependency",
                    confidence=0.72 if availability.get("triggered") else 0.58,
                    rationale=service_error.get("reason", "top error service elevated"),
                    validation_plan=[
                        "Check latest application trace for failing downstream span",
                        "Compare target deployment health with frontend error surge",
                    ],
                )
            )

        if (error_ratio.get("triggered") or service_latency.get("triggered")) and not availability.get("triggered"):
            hypotheses.append(
                Hypothesis(
                    id="performance_degradation",
                    title="Performance degradation under load",
                    suspected_service=service_latency.get("service") or service_error.get("service") or target_deployment,
                    category="performance",
                    confidence=0.62 if service_latency.get("triggered") else 0.55,
                    rationale=service_latency.get("reason") or error_ratio.get("reason", "global error ratio elevated"),
                    validation_plan=[
                        "Compare target service traffic and error rates",
                        "Inspect p99 latency on the suspected service",
                        "Inspect recent traces for slow or failing spans",
                        "Check pod restarts and events for instability",
                    ],
                )
            )

        if not hypotheses:
            hypotheses.append(
                Hypothesis(
                    id="no_strong_hypothesis",
                    title="No strong hypothesis from detector output",
                    suspected_service=target_deployment,
                    category="unknown",
                    confidence=0.2,
                    rationale=detection.get("summary", "no detector triggered"),
                    validation_plan=["Gather more metrics and traces before acting"],
                )
            )

        hypotheses.sort(key=lambda item: item.confidence, reverse=True)
        return hypotheses
