from __future__ import annotations

from typing import Any, Dict, List

from agent_graph.knowledge.topology import downstream_dependencies, service_context, topology_summary
from agent_graph.reasoning.heuristic import HeuristicHypothesizer
from agent_graph.reasoning.llm import LLMBasedHypothesizer
from agent_graph.schemas import Hypothesis


class Hypothesizer:
    def __init__(self, mode: str = "heuristic") -> None:
        self.mode = mode
        self.llm = LLMBasedHypothesizer()
        self.heuristic = HeuristicHypothesizer()

    def run(self, detection: Dict[str, Any], target_deployment: str) -> List[Hypothesis]:
        if self.mode == "llm" and self.llm.available():
            try:
                return self.llm.rank(detection, target_deployment, self._knowledge_context(detection, target_deployment))
            except Exception:
                pass
        return self._enrich(self.heuristic.rank(detection, target_deployment), detection, target_deployment)

    def _knowledge_context(self, detection: Dict[str, Any], target_deployment: str) -> Dict[str, Any]:
        top_error_service = ""
        for finding in detection.get("findings", []):
            if finding.get("name") == "service_error_rate":
                top_error_service = finding.get("service", "")
                break
        services = [service for service in [target_deployment, top_error_service] if service]
        topology = {service: service_context(service) for service in services}
        adjacent = {
            service: {
                "downstream_dependencies": downstream_dependencies(service),
            }
            for service in services
        }
        return {
            "topology": topology,
            "adjacent": adjacent,
        }

    def _enrich(self, hypotheses: List[Hypothesis], detection: Dict[str, Any], target_deployment: str) -> List[Hypothesis]:
        top_error_service = ""
        for finding in detection.get("findings", []):
            if finding.get("name") == "service_error_rate":
                top_error_service = finding.get("service", "")
                break

        enriched: List[Hypothesis] = []
        for hypothesis in hypotheses:
            rationale = hypothesis.rationale
            validation_plan = list(hypothesis.validation_plan)
            if hypothesis.id == "deployment_unavailable" and hypothesis.suspected_service:
                rationale = (
                    f"{hypothesis.rationale}. "
                    f"Topology context: {topology_summary(hypothesis.suspected_service)}"
                )
            if (
                hypothesis.id == "frontend_symptom_from_downstream_failure"
                and top_error_service == "frontend"
                and target_deployment
            ):
                deps = downstream_dependencies("frontend")
                rationale = (
                    f"{hypothesis.rationale}. "
                    f"Frontend is the user-facing surface and depends on {deps}; "
                    f"{target_deployment} is a plausible downstream root cause."
                )
                validation_plan.append(
                    f"Prioritize dependency evidence for frontend downstream services: {deps}"
                )
            hypothesis.rationale = rationale
            hypothesis.validation_plan = validation_plan
            enriched.append(hypothesis)
        return enriched
