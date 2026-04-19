from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_graph.diagnostic_agent import DiagnosticAgent, DiagnosticEvidenceLedger


class FakeACI:
    jaeger_enabled = True

    def __init__(self) -> None:
        self.submitted: Dict[str, Any] = {}

    def get_k8s_state(self, service: str) -> Dict[str, Any]:
        return {
            "call_id": f"k8s-{service}",
            "status": "ok",
            "summary": f"{service} workload and service wiring are available.",
            "key_facts": [f"{service} pods ready", "Service targetPort aligns with container port"],
            "anomalies": [],
            "negative_evidence": ["No rollout/probe/image-pull anomaly visible"],
            "observability_gaps": [],
            "raw_refs": [{"tool": "get_k8s_state"}],
        }

    def get_metrics(self, service: str, lookback_minutes: int = 5) -> Dict[str, Any]:
        return {
            "call_id": f"metrics-{service}",
            "status": "ok",
            "summary": "Latency elevated without app-local CPU/memory saturation.",
            "key_facts": ["p95 latency elevated", "App-local CPU and memory are not saturated"],
            "anomalies": [{"type": "latency_or_errors_without_app_resource_saturation"}],
            "negative_evidence": ["No OOMKilled evidence", "No CPU throttling saturation"],
            "observability_gaps": [],
            "raw_refs": [{"tool": "get_metrics"}],
        }

    def get_logs(self, service: str, tail_lines: int = 100) -> Dict[str, Any]:
        return {
            "call_id": f"logs-{service}",
            "status": "anomalous",
            "summary": "Logs show dependency connection failures.",
            "key_facts": ["frontend logs contain timeouts contacting cartservice"],
            "anomalies": [{"type": "connection_failures_observed", "scope": "logs"}],
            "negative_evidence": [],
            "observability_gaps": [],
            "raw_refs": [{"tool": "get_logs"}],
        }

    def get_dependency_traces(self, service: str, entry_service: str = "frontend", lookback_minutes: int = 5) -> Dict[str, Any]:
        return {
            "call_id": f"dep-{service}",
            "status": "anomalous",
            "summary": f"Dependency traces show frontend to {service} failures.",
            "key_facts": [f"frontend -> {service} spans fail"],
            "anomalies": [{"type": "dependency_edge_failure", "edge": f"frontend->{service}"}],
            "negative_evidence": ["No frontend service wiring mismatch"],
            "observability_gaps": [],
            "raw_refs": [{"tool": "get_dependency_traces"}],
        }

    def get_cluster_resource_context(self, service: str) -> Dict[str, Any]:
        return {
            "call_id": f"cluster-{service}",
            "status": "ok",
            "summary": "No non-application pressure workload is visible.",
            "key_facts": [],
            "anomalies": [],
            "negative_evidence": ["No external resource pressure evidence"],
            "observability_gaps": [],
            "raw_refs": [{"tool": "get_cluster_resource_context"}],
        }

    def submit_solution(
        self,
        root_cause: str,
        action_taken: str,
        confidence: float,
        evidence: List[str],
        fault_class: str = "",
        affected_service: str = "",
        action_type: str = "",
    ) -> Dict[str, Any]:
        self.submitted = {
            "call_id": "submit-1",
            "solution_logged": True,
            "evidence_valid": True,
            "error": None,
            "root_cause": root_cause,
            "action_taken": action_taken,
            "fault_class": fault_class,
            "affected_service": affected_service,
            "action_type": action_type,
            "confidence": confidence,
            "evidence": evidence,
        }
        return dict(self.submitted)


class FakeClient:
    def __init__(self) -> None:
        self.names: List[str] = []

    def complete_json(self, *, name: str, schema: Dict[str, Any], prompt: Dict[str, Any]) -> Dict[str, Any]:
        self.names.append(name)
        if name == "diagnostic_hypotheses":
            return {
                "symptom_scope": "dependency_path_trace_centered",
                "affected_service_candidates": ["cartservice"],
                "hypotheses": [
                    {
                        "fault_class": "native_dependency_bad_endpoint",
                        "category": "dependency_path_trace_centered",
                        "affected_service": "cartservice",
                        "supporting_evidence": ["logs show cartservice connection failures"],
                        "contradicting_evidence": ["cartservice pods are ready"],
                        "missing_evidence": ["dependency traces"],
                        "score": 0.7,
                    }
                ],
                "distinguishing_question": "Do traces localize failures to cartservice?",
                "recommended_next_tools": ["get_dependency_traces"],
            }
        return {
            "ready_to_submit": True,
            "chosen_fault_class": "native_dependency_bad_endpoint",
            "why_this_class": "Traces and logs point to cartservice dependency failures.",
            "why_not_nearest_alternative": "Service wiring and app-local resource saturation are not supported.",
            "missing_evidence": [],
            "next_tool": {"tool": "none", "service": "cartservice"},
            "solution": {
                "root_cause": "Frontend requests fail when calling cartservice due to a bad dependency endpoint.",
                "action_taken": "Roll back or restore the deployed dependency endpoint configuration for cartservice.",
                "fault_class": "native_dependency_bad_endpoint",
                "affected_service": "cartservice",
                "action_type": "rollout_undo",
                "confidence": 0.82,
                "evidence": ["get_logs(frontend)", "get_dependency_traces(cartservice)"],
            },
        }


def test_ledger_requires_trace_for_dependency_fault() -> None:
    ledger = DiagnosticEvidenceLedger()
    ledger.add(tool="get_logs", service="frontend", output={"key_facts": ["timeout contacting cartservice"]})

    assert "dependency traces have not been inspected" in ledger.missing_for_fault("native_dependency_bad_endpoint")

    ledger.add(tool="get_dependency_traces", service="cartservice", output={"key_facts": ["frontend -> cartservice fails"]})
    assert ledger.missing_for_fault("native_dependency_bad_endpoint") == []


def test_diagnostic_agent_collects_follow_up_trace_and_submits() -> None:
    agent = object.__new__(DiagnosticAgent)
    agent.aci = FakeACI()
    agent.provider = "test"
    agent.model = "fake"
    agent.max_steps = 12
    agent.diagnosis_only = True
    agent.step_callback = None
    agent.client = FakeClient()

    result = DiagnosticAgent.run(
        agent,
        "An incident has been detected.",
        initial_context={"suspicious_services": ["frontend"]},
    )

    tools = [step["tool_called"] for step in result["steps"]]
    assert tools[:3] == ["get_k8s_state", "get_metrics", "get_logs"]
    assert "get_dependency_traces" in tools
    assert tools[-1] == "submit_solution"
    assert result["solution"]["fault_class"] == "native_dependency_bad_endpoint"
    assert result["solution"]["action_type"] == "rollout_undo"


def test_diagnostic_agent_skips_follow_up_when_direct_hypothesis_is_complete() -> None:
    agent = object.__new__(DiagnosticAgent)
    agent.ledger = DiagnosticEvidenceLedger()
    agent._initial_context = {"suspicious_services": ["productcatalogservice"]}
    agent.ledger.add(
        tool="get_k8s_state",
        service="productcatalogservice",
        output={
            "key_facts": ["Service targetPort=1; container exposes 3550"],
            "anomalies": [{"type": "port_inconsistency", "scope": "service"}],
        },
    )
    hypotheses = {
        "affected_service_candidates": ["productcatalogservice"],
        "recommended_next_tools": ["get_dependency_traces"],
        "hypotheses": [
            {
                "fault_class": "native_service_port_mismatch",
                "affected_service": "productcatalogservice",
                "missing_evidence": [],
                "score": 0.9,
            },
            {
                "fault_class": "native_dependency_bad_endpoint",
                "affected_service": "productcatalogservice",
                "missing_evidence": ["dependency traces"],
                "score": 0.3,
            },
        ],
    }

    assert DiagnosticAgent._plan_follow_up_tools(agent, hypotheses, limit=3) == []


def test_diagnostic_agent_accepts_complete_supported_verifier_solution() -> None:
    agent = object.__new__(DiagnosticAgent)
    agent.ledger = DiagnosticEvidenceLedger()
    agent.ledger.add(
        tool="get_k8s_state",
        service="productcatalogservice",
        output={
            "key_facts": ["Service targetPort=1; container exposes 3550"],
            "anomalies": [{"type": "port_inconsistency", "scope": "service"}],
        },
    )
    verification = {
        "ready_to_submit": False,
        "chosen_fault_class": "native_service_port_mismatch",
        "solution": {
            "root_cause": "Service targetPort mismatch.",
            "action_taken": "Patch Service targetPort.",
            "fault_class": "native_service_port_mismatch",
            "affected_service": "productcatalogservice",
            "action_type": "patch_service_target_port",
        },
    }

    assert DiagnosticAgent._verification_has_complete_supported_solution(agent, verification)
