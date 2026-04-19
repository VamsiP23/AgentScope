from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_graph.react_agent import ReActAgent


class DummyAci:
    jaeger_enabled = True

    def get_cluster_resource_context(self, service: str) -> dict:
        return {"service": service}

    def submit_solution(
        self,
        root_cause: str,
        action_taken: str,
        confidence: float,
        evidence: list[str],
        fault_class: str = "",
        affected_service: str = "",
        action_type: str = "",
    ) -> dict:
        return {
            "call_id": "submit-1",
            "solution_logged": True,
            "evidence_valid": True,
            "root_cause": root_cause,
            "action_taken": action_taken,
            "fault_class": fault_class,
            "affected_service": affected_service,
            "action_type": action_type,
            "confidence": confidence,
            "evidence": evidence,
        }


def bounded_agent(trace: list[dict] | None = None) -> ReActAgent:
    agent = object.__new__(ReActAgent)
    agent.aci = DummyAci()
    agent.agent_variant = "bounded_react"
    agent.bounded_mode = True
    agent.trace = list(trace or [])
    return agent


def test_bounded_react_blocks_dependency_submit_without_trace() -> None:
    agent = bounded_agent(
        [
            {"tool_called": "get_k8s_state", "inputs": {"service": "frontend"}, "output": {}},
            {"tool_called": "get_logs", "inputs": {"service": "frontend"}, "output": {}},
        ]
    )

    violation = agent._bounded_submit_violation(
        {
            "tool": "submit_solution",
            "fault_class": "native_dependency_bad_endpoint",
            "root_cause": "frontend is failing on a downstream dependency endpoint",
            "action_type": "rollout_undo",
        }
    )

    assert violation is not None
    assert violation["type"] == "bounded_submit_missing_trace_evidence"
    assert violation["disallow_tool"] == "submit_solution"


def test_bounded_react_allows_dependency_submit_after_trace() -> None:
    agent = bounded_agent(
        [
            {"tool_called": "get_k8s_state", "inputs": {"service": "frontend"}, "output": {}},
            {"tool_called": "get_dependency_traces", "inputs": {"service": "frontend"}, "output": {}},
        ]
    )

    violation = agent._bounded_submit_violation(
        {
            "tool": "submit_solution",
            "fault_class": "native_dependency_bad_endpoint",
            "root_cause": "frontend is failing on a downstream dependency endpoint",
            "action_type": "rollout_undo",
        }
    )

    assert violation is None


def test_bounded_react_blocks_incoherent_dependency_action() -> None:
    agent = bounded_agent(
        [
            {"tool_called": "get_k8s_state", "inputs": {"service": "frontend"}, "output": {}},
            {"tool_called": "get_dependency_traces", "inputs": {"service": "frontend"}, "output": {}},
            {"tool_called": "get_metrics", "inputs": {"service": "frontend"}, "output": {}},
        ]
    )

    violation = agent._bounded_submit_violation(
        {
            "tool": "submit_solution",
            "fault_class": "native_dependency_bad_endpoint",
            "root_cause": "frontend dependency endpoint is misconfigured",
            "action_type": "patch_resources",
        }
    )

    assert violation is not None
    assert violation["type"] == "bounded_submit_incoherent_action"
    assert violation["expected_action_type"] == "rollout_undo"


def test_bounded_react_blocks_resource_submit_without_metrics() -> None:
    agent = bounded_agent(
        [
            {"tool_called": "get_k8s_state", "inputs": {"service": "checkoutservice"}, "output": {}},
            {"tool_called": "get_logs", "inputs": {"service": "checkoutservice"}, "output": {}},
        ]
    )

    violation = agent._bounded_submit_violation(
        {
            "tool": "submit_solution",
            "fault_class": "native_cpu_limit_throttle",
            "root_cause": "checkoutservice has CPU throttling",
            "action_type": "patch_resources",
        }
    )

    assert violation is not None
    assert violation["type"] == "bounded_submit_missing_metrics_evidence"


def test_bounded_react_blocks_service_port_submit_without_service_scoped_port_evidence() -> None:
    agent = bounded_agent(
        [
            {
                "tool_called": "get_k8s_state",
                "inputs": {"service": "frontend"},
                "output": {
                    "anomalies": [
                        {"type": "port_inconsistency", "scope": "dependency_config"},
                    ]
                },
            },
            {"tool_called": "get_logs", "inputs": {"service": "frontend"}, "output": {}},
        ]
    )

    violation = agent._bounded_submit_violation(
        {
            "tool": "submit_solution",
            "fault_class": "native_service_port_mismatch",
            "root_cause": "frontend is configured to connect to cartservice on port 1",
            "action_type": "patch_service_target_port",
        }
    )

    assert violation is not None
    assert violation["type"] == "bounded_submit_missing_service_port_evidence"


def test_bounded_react_allows_service_port_submit_with_service_scoped_port_evidence() -> None:
    agent = bounded_agent(
        [
            {
                "tool_called": "get_k8s_state",
                "inputs": {"service": "productcatalogservice"},
                "output": {
                    "anomalies": [
                        {"type": "port_inconsistency", "scope": "service"},
                    ]
                },
            },
            {"tool_called": "get_logs", "inputs": {"service": "productcatalogservice"}, "output": {}},
        ]
    )

    violation = agent._bounded_submit_violation(
        {
            "tool": "submit_solution",
            "fault_class": "native_service_port_mismatch",
            "root_cause": "productcatalogservice Service targetPort does not match exposed container port",
            "action_type": "patch_service_target_port",
        }
    )

    assert violation is None


def test_bounded_react_blocks_stress_submit_without_cluster_context_when_available() -> None:
    agent = bounded_agent(
        [
            {"tool_called": "get_k8s_state", "inputs": {"service": "frontend"}, "output": {}},
            {"tool_called": "get_metrics", "inputs": {"service": "frontend"}, "output": {}},
        ]
    )

    violation = agent._bounded_submit_violation(
        {
            "tool": "submit_solution",
            "fault_class": "native_cpu_pressure_stress_job",
            "root_cause": "external CPU pressure from a stress job",
            "action_type": "delete_stress_job",
        }
    )

    assert violation is not None
    assert violation["type"] == "bounded_submit_missing_cluster_resource_context"


def test_bounded_react_allows_stress_submit_after_metrics_and_cluster_context() -> None:
    agent = bounded_agent(
        [
            {"tool_called": "get_k8s_state", "inputs": {"service": "frontend"}, "output": {}},
            {"tool_called": "get_metrics", "inputs": {"service": "frontend"}, "output": {}},
            {"tool_called": "get_cluster_resource_context", "inputs": {"service": "frontend"}, "output": {}},
        ]
    )

    violation = agent._bounded_submit_violation(
        {
            "tool": "submit_solution",
            "fault_class": "native_cpu_pressure_stress_job",
            "root_cause": "external CPU pressure from a stress job",
            "action_type": "delete_stress_job",
        }
    )

    assert violation is None


def test_react_submit_accepts_fields_nested_in_tool_input() -> None:
    agent = bounded_agent()

    step = agent._execute_step(
        1,
        {
            "tool": "submit_solution",
            "tool_input": {
                "root_cause": "external CPU pressure",
                "action_taken": "delete the stress workload",
                "fault_class": "native_cpu_pressure_stress_job",
                "affected_service": "frontend",
                "action_type": "delete_stress_job",
                "confidence": 0.9,
                "evidence": ["call-1"],
            },
        },
    )

    assert step["output"]["root_cause"] == "external CPU pressure"
    assert step["output"]["fault_class"] == "native_cpu_pressure_stress_job"
    assert step["output"]["action_type"] == "delete_stress_job"
    assert step["output"]["evidence"] == ["call-1"]
