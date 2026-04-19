from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarking.replay import ReplayDataset
from scripts.run_compact_diagnosis import build_prompt, compact_records


def test_compact_records_only_include_evidence_tools() -> None:
    dataset = ReplayDataset(
        path=Path("native_service_port_mismatch_productcatalogservice_001.json"),
        metadata={"task_id": "native_service_port_mismatch_productcatalogservice_001"},
        initial_context={"summary": "service degraded"},
        calls=[
            {"method": "get_k8s_state", "inputs": {"service": "svc"}, "outputs": {"service": "svc"}},
            {"method": "restart_pod", "inputs": {"service": "svc"}, "outputs": {"executed": True}},
            {"method": "submit_solution", "inputs": {}, "outputs": {"fault_class": "native_service_port_mismatch"}},
            {"method": "get_trace_by_id", "inputs": {"trace_id": "abc"}, "outputs": {"trace_id": "abc"}},
        ],
    )

    rows = compact_records(dataset, max_records=10)

    assert [row["tool"] for row in rows] == ["get_k8s_state"]


def test_compact_prompt_does_not_embed_problem_id() -> None:
    dataset = ReplayDataset(
        path=Path("native_service_port_mismatch_productcatalogservice_001.json"),
        metadata={"task_id": "native_service_port_mismatch_productcatalogservice_001"},
        initial_context={"summary": "service degraded"},
        calls=[],
    )

    prompt = build_prompt(dataset, evidence=[])

    assert "problem_id_for_tracking_only" not in prompt
    assert "native_service_port_mismatch_productcatalogservice" not in str(prompt)


def test_replay_load_adds_sanitized_cluster_resource_context(tmp_path: Path) -> None:
    source = tmp_path / "source_run"
    source.mkdir()
    (source / "evidence_report.json").write_text(
        json.dumps(
            {
                "detector_snapshot": {
                    "suspicious_services": ["frontend"],
                    "findings": [
                        {
                            "name": "native_stress_job",
                            "service": "frontend",
                            "details": {
                                "active_stress_jobs": [
                                    {
                                        "pod": "agentscope-cpu-pressure-abc",
                                        "job": "agentscope-cpu-pressure",
                                        "phase": "Running",
                                        "node": "worker-a",
                                    }
                                ]
                            },
                        }
                    ],
                }
            }
        )
    )
    episode = tmp_path / "episode.json"
    episode.write_text(
        json.dumps(
            {
                "task_id": "native_cpu_pressure_stress_job_001",
                "initial_context": {"summary": "frontend degraded", "suspicious_services": ["frontend"]},
                "provenance": {"source_run_dir": str(source), "namespace": "default"},
                "phases": [
                    {
                        "phase_id": 0,
                        "label": "initial_degradation",
                        "tool_responses": {
                            "get_metrics|service=frontend": {
                                "service": "frontend",
                                "metrics": {
                                    "cpu_utilization_pct_of_limit": 25.0,
                                    "memory_utilization_pct_of_limit": 20.0,
                                    "cpu_throttling_ratio": 0.01,
                                },
                            }
                        },
                        "observability": {},
                        "transitions": [],
                    }
                ],
            }
        )
    )

    dataset = ReplayDataset.load(episode)
    rows = compact_records(dataset, max_records=10)
    context = next(row for row in rows if row["tool"] == "get_cluster_resource_context")

    assert context["evidence"]["status"] == "anomalous"
    assert any(item.get("resource") == "cpu" for item in context["evidence"]["anomalies"])
    assert "native_stress_job" not in str(context)
    assert "agentscope-cpu-pressure" not in str(context)
