from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_graph.reasoning.llm import BaseJSONClient
from agent_graph.structured_compact_agent import (
    build_triage_prompt,
    collect_compact_evidence,
    group_evidence_by_channel,
    run_structured_compact_diagnosis,
)
from benchmarking.replay import ReplayDataset


class FakeStructuredClient(BaseJSONClient):
    def __init__(self) -> None:
        super().__init__(model="fake", api_key="fake")
        self.names = []

    def complete_json(self, *, name: str, schema: Dict[str, Any], prompt: Dict[str, Any]) -> Dict[str, Any]:
        self.names.append(name)
        if name == "structured_compact_triage":
            return {
                "suspected_categories": ["service_wiring_configuration"],
                "needed_evidence": ["k8s_state", "service_config"],
                "key_observations": ["Service targetPort and container port disagree."],
                "why": "Service wiring anomaly is visible in compact Kubernetes evidence.",
            }
        if name == "structured_compact_candidate_analysis":
            return {
                "positive_facts": ["Service targetPort=1 while container exposes 3550."],
                "anomalies": ["Service port alignment mismatch."],
                "negative_evidence": ["Pods are ready."],
                "observability_gaps": [],
                "candidates": [
                    {
                        "fault_class": "native_service_port_mismatch",
                        "affected_service": "productcatalogservice",
                        "action_type": "patch_service_target_port",
                        "supporting_evidence": ["get_k8s_state(productcatalogservice)"],
                        "contradicting_evidence": [],
                        "score": 0.95,
                    }
                ],
                "rejected_candidates": ["native_service_selector_mismatch: selected pods exist."],
            }
        return {
            "root_cause": "Service targetPort 1 does not match container port 3550.",
            "action_taken": "Patch productcatalogservice Service targetPort to 3550.",
            "fault_class": "native_service_port_mismatch",
            "affected_service": "productcatalogservice",
            "action_type": "patch_service_target_port",
            "confidence": 0.95,
            "evidence": ["get_k8s_state(productcatalogservice)"],
        }


def _dataset() -> ReplayDataset:
    return ReplayDataset(
        path=Path("native_service_port_mismatch_productcatalogservice_001.json"),
        metadata={"task_id": "native_service_port_mismatch_productcatalogservice_001"},
        initial_context={"summary": "productcatalogservice is unavailable through its Service"},
        calls=[
            {
                "method": "get_k8s_state",
                "inputs": {"service": "productcatalogservice"},
                "outputs": {
                    "service": "productcatalogservice",
                    "desired_replicas": 1,
                    "available_replicas": 1,
                    "service_config_summary": {
                        "selector": {"app": "productcatalogservice"},
                        "selected_pod_count": 1,
                        "deployment_pod_count": 1,
                        "service_ports": [{"port": 3550, "targetPort": 1}],
                        "container_ports": [{"containerPort": 3550}],
                        "service_port_alignment": {
                            "aligned": False,
                            "mismatches": [{"service_port": 3550, "targetPort": 1}],
                        },
                    },
                },
            },
            {
                "method": "get_logs",
                "inputs": {"service": "productcatalogservice"},
                "outputs": {"service": "productcatalogservice", "error_lines": []},
            },
            {"method": "submit_solution", "inputs": {}, "outputs": {"fault_class": "answer_leak"}},
        ],
    )


def test_group_evidence_by_channel() -> None:
    evidence = collect_compact_evidence(_dataset(), max_records=10)
    groups = group_evidence_by_channel(evidence)

    assert len(groups["k8s_state"]) == 1
    assert len(groups["logs"]) == 1
    assert all(item["tool"] != "submit_solution" for item in evidence)


def test_structured_prompt_does_not_embed_problem_id() -> None:
    dataset = _dataset()
    evidence = collect_compact_evidence(dataset, max_records=10)
    prompt = build_triage_prompt(dataset, group_evidence_by_channel(evidence))

    assert "native_service_port_mismatch_productcatalogservice" not in str(prompt)


def test_structured_compact_runs_three_stages() -> None:
    client = FakeStructuredClient()
    result = run_structured_compact_diagnosis(
        client=client,
        dataset=_dataset(),
        max_evidence_records=10,
    )

    assert client.names == [
        "structured_compact_triage",
        "structured_compact_candidate_analysis",
        "structured_compact_solution",
    ]
    assert result["solution"]["fault_class"] == "native_service_port_mismatch"
    assert result["steps"][-1]["tool_called"] == "submit_solution"
    assert result["steps"][-1]["output"]["solution_logged"] is True
