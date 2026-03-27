from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

from agent_graph.knowledge.topology import downstream_dependencies, topology_summary, upstream_surfaces
from agent_graph.reasoning.llm import ResponsesJSONClient
from agent_graph.schemas import EvidenceItem, Hypothesis, ResearchStep
from agent_graph.tools.jaeger import JaegerTools
from agent_graph.tools.kubernetes import KubernetesTools
from agent_graph.tools.prometheus import PrometheusTools
from detectors.schemas import DetectionConfig


class Researcher:
    def __init__(
        self,
        config: DetectionConfig,
        prom: PrometheusTools,
        k8s: KubernetesTools,
        jaeger: JaegerTools,
        mode: str = "heuristic",
    ) -> None:
        self.config = config
        self.prom = prom
        self.k8s = k8s
        self.jaeger = jaeger
        self.mode = mode
        self.llm = ResponsesJSONClient()

    def run(self, hypotheses: List[Hypothesis], max_tool_calls: int = 5) -> Tuple[List[EvidenceItem], List[ResearchStep], str]:
        if self.mode == "llm":
            if not self.llm.available():
                raise RuntimeError("LLM mode requested but OPENAI_API_KEY is not set")
            try:
                evidence, steps = self._run_agentic(hypotheses, max_tool_calls=max_tool_calls)
                return evidence, steps, "llm"
            except Exception as exc:
                raise RuntimeError(f"LLM researcher failed: {exc}") from exc
        evidence, steps = self._run_heuristic(hypotheses)
        return evidence, steps, "heuristic"

    def _primary_service(self, hypotheses: List[Hypothesis]) -> str:
        return (hypotheses[0].suspected_service if hypotheses else "") or self.config.target_deployment

    def _default_symptom_services(self, service: str) -> List[str]:
        if not service:
            return ["frontend"]
        return list(dict.fromkeys(["frontend", *upstream_surfaces(service)]))

    def _tool_registry(self, primary_service: str, symptom_service: str) -> Dict[str, Callable[[Dict[str, Any]], List[EvidenceItem]]]:
        return {
            "service_topology": lambda _: [self._service_topology(primary_service)],
            "deployment_health": lambda params: [self._deployment_health(params.get("service") or primary_service)],
            "pod_status": lambda params: [self._pod_status(params.get("service") or primary_service)],
            "top_error_services": lambda _: [self._top_error_services()],
            "global_error_ratio": lambda _: [self._global_error_ratio()],
            "service_rps": lambda _: [self._service_rps()],
            "failing_traces": lambda params: [self._failing_traces(params.get("service") or symptom_service)],
            "downstream_failure_summary": lambda params: [self._downstream_failure_summary(params.get("service") or symptom_service)],
            "dependency_trace": lambda params: [self._dependency_trace(params.get("service") or primary_service)],
            "recent_events": lambda _: [self._recent_events()],
            "restart_history": lambda _: [self._restart_history()],
        }

    def _run_heuristic(self, hypotheses: List[Hypothesis]) -> Tuple[List[EvidenceItem], List[ResearchStep]]:
        evidence: List[EvidenceItem] = []
        steps: List[ResearchStep] = []
        primary_service = self._primary_service(hypotheses)
        symptom_service = self._default_symptom_services(primary_service)[0]
        plan: List[Tuple[str, Dict[str, Any], str]] = [
            ("service_topology", {}, "Establish service context before reading signals."),
            ("deployment_health", {"service": primary_service}, "Check whether the target deployment is actually unhealthy."),
            ("pod_status", {"service": primary_service}, "Inspect active pods and rollout progression."),
            ("top_error_services", {}, "Measure which service is surfacing the most errors."),
            ("global_error_ratio", {}, "Measure whether the incident is globally visible."),
            ("failing_traces", {"service": symptom_service}, "Look for failing traces from the symptom surface."),
            ("downstream_failure_summary", {"service": symptom_service}, "Locate the failing hop in the trace graph."),
            ("dependency_trace", {"service": primary_service}, "Inspect downstream dependencies of the suspected service."),
            ("restart_history", {}, "Check for restart-driven instability."),
            ("recent_events", {}, "Look for Kubernetes warnings and rollout failures."),
        ]
        registry = self._tool_registry(primary_service, symptom_service)
        for tool_name, params, rationale in plan:
            items = registry[tool_name](params)
            evidence.extend(items)
            steps.append(
                ResearchStep(
                    tool=tool_name,
                    params=params,
                    rationale=rationale,
                    evidence_names=[item.name for item in items],
                )
            )
        return evidence, steps

    def _run_agentic(self, hypotheses: List[Hypothesis], max_tool_calls: int) -> Tuple[List[EvidenceItem], List[ResearchStep]]:
        evidence: List[EvidenceItem] = []
        steps: List[ResearchStep] = []
        primary_service = self._primary_service(hypotheses)
        symptom_service = self._default_symptom_services(primary_service)[0]
        registry = self._tool_registry(primary_service, symptom_service)
        available_tools = sorted(registry.keys())

        for _ in range(max(1, max_tool_calls)):
            prompt = {
                "task": "Choose the next diagnostic tool call for incident research.",
                "target_deployment": self.config.target_deployment,
                "primary_service": primary_service,
                "symptom_service": symptom_service,
                "hypotheses": [hyp.to_dict() for hyp in hypotheses],
                "evidence_collected": [item.to_dict() for item in evidence],
                "available_tools": available_tools,
                "requirements": {
                    "choose_one_tool_per_turn": True,
                    "prefer_lower_cost_tools_before_redundant_trace_queries": True,
                    "return_done_true_when_evidence_is_sufficient_to_judge_support": True,
                },
            }
            decision = self.llm.complete_json(
                name="research_decision",
                schema={
                    "type": "object",
                    "properties": {
                        "done": {"type": "boolean"},
                        "tool": {"type": "string"},
                        "params": {"type": "object", "additionalProperties": True},
                        "rationale": {"type": "string"},
                    },
                    "required": ["done", "tool", "params", "rationale"],
                    "additionalProperties": False,
                },
                prompt=prompt,
            )
            if decision.get("done", False):
                break
            tool_name = str(decision.get("tool", "")).strip()
            if tool_name not in registry:
                break
            params = decision.get("params", {}) or {}
            items = registry[tool_name](params)
            evidence.extend(items)
            steps.append(
                ResearchStep(
                    tool=tool_name,
                    params=params,
                    rationale=str(decision.get("rationale", "")),
                    evidence_names=[item.name for item in items],
                )
            )

        if not evidence:
            return self._run_heuristic(hypotheses)
        return evidence, steps

    def _service_topology(self, service: str) -> EvidenceItem:
        summary = topology_summary(service) if service else "no target deployment supplied"
        return EvidenceItem(
            source="knowledge",
            name="service_topology",
            summary=summary,
            details={
                "service": service,
                "downstream_dependencies": downstream_dependencies(service) if service else [],
                "upstream_surfaces": upstream_surfaces(service) if service else [],
            },
        )

    def _deployment_health(self, service: str) -> EvidenceItem:
        dep = self.k8s.deployment_health(self.config.namespace, service) if service else {}
        supports: List[str] = []
        contradicts: List[str] = []
        if dep:
            if dep.get("healthy", True):
                contradicts.append("deployment_unavailable")
            else:
                supports.append("deployment_unavailable")
        return EvidenceItem(
            source="kubernetes",
            name=f"deployment_health:{service or 'unknown'}",
            summary=f"deployment {service} available={dep.get('available', 0)} desired={dep.get('desired', 0)}",
            supports=supports,
            contradicts=contradicts,
            details=dep,
        )

    def _pod_status(self, service: str) -> EvidenceItem:
        status = self.k8s.deployment_pod_status(self.config.namespace, service) if service else {}
        supports: List[str] = []
        if status and status.get("pod_count", 0) == 0:
            supports.append("deployment_unavailable")
        return EvidenceItem(
            source="kubernetes",
            name=f"pod_status:{service or 'unknown'}",
            summary=(
                f"pods={status.get('pod_count', 0)} ready={status.get('ready_pod_count', 0)} "
                f"progressing={status.get('progressing', False)}"
            ),
            supports=supports,
            details=status,
        )

    def _top_error_services(self) -> EvidenceItem:
        top_errors = self.prom.top_error_services(self.config.window, limit=5)
        return EvidenceItem(
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

    def _global_error_ratio(self) -> EvidenceItem:
        global_errors = self.prom.global_error_ratio(self.config.window)
        supports = ["performance_degradation"] if global_errors["error_ratio"] >= self.config.error_ratio_threshold else []
        return EvidenceItem(
            source="prometheus",
            name="global_error_ratio",
            summary=f"error_ratio={global_errors['error_ratio']:.3f} total_rps={global_errors['total_rps']:.3f}",
            supports=supports,
            details=global_errors,
        )

    def _service_rps(self) -> EvidenceItem:
        rows = self.prom.service_rps(self.config.window, limit=10)
        return EvidenceItem(
            source="prometheus",
            name="service_rps",
            summary=(f"highest traffic service: {rows[0]['service_name']} at {rows[0]['rps']:.3f} rps" if rows else "no traffic rows"),
            details={"service_rps": rows},
        )

    def _failing_traces(self, service: str) -> EvidenceItem:
        trace = self.jaeger.recent_failing_traces(service, limit=10, lookback="1h")
        supports = ["frontend_symptom_from_downstream_failure"] if trace.get("trace_found", False) else []
        return EvidenceItem(
            source="jaeger",
            name=f"failing_traces:{service}",
            summary=trace.get("summary", f"no failing trace summary for {service}"),
            supports=supports,
            details=trace,
        )

    def _downstream_failure_summary(self, service: str) -> EvidenceItem:
        summary = self.jaeger.failing_downstream_summary(service, limit=10, lookback="1h")
        supports: List[str] = []
        if summary.get("downstream_counts"):
            supports.extend(["dependency_outage", "frontend_symptom_from_downstream_failure"])
        return EvidenceItem(
            source="jaeger",
            name=f"downstream_failure_summary:{service}",
            summary=summary.get("summary", f"no downstream summary for {service}"),
            supports=supports,
            details=summary,
        )

    def _dependency_trace(self, service: str) -> EvidenceItem:
        dependency_summaries = []
        support_ids: List[str] = []
        for dependency in downstream_dependencies(service):
            trace = self.jaeger.failing_downstream_summary(dependency, limit=10, lookback="1h")
            dependency_summaries.append({"dependency": dependency, "summary": trace})
            if trace.get("trace_found", False):
                support_ids.append("dependency_outage")
        return EvidenceItem(
            source="jaeger",
            name=f"dependency_trace:{service or 'unknown'}",
            summary=(
                f"dependency trace evidence across {len(dependency_summaries)} downstream services"
                if dependency_summaries
                else "no downstream dependencies to inspect"
            ),
            supports=support_ids,
            details={"dependencies": dependency_summaries},
        )

    def _restart_history(self) -> EvidenceItem:
        restarts = self.k8s.top_pod_restarts(self.config.namespace, limit=5)
        return EvidenceItem(
            source="kubernetes",
            name="restart_history",
            summary=f"pods with restart history={len(restarts)}",
            details={"top_pod_restarts": restarts},
        )

    def _recent_events(self) -> EvidenceItem:
        events = self.k8s.recent_events(self.config.namespace, limit=10)
        supports = []
        if any("Back-off" in item.get("reason", "") or "Unhealthy" in item.get("reason", "") for item in events):
            supports.append("deployment_unavailable")
        return EvidenceItem(
            source="kubernetes",
            name="recent_events",
            summary=f"recent events collected={len(events)}",
            supports=supports,
            details={"events": events},
        )
