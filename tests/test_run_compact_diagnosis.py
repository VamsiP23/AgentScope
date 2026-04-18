from __future__ import annotations

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
