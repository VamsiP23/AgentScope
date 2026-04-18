from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarking.results import aggregate_evaluations, load_episode_taxonomy, taxonomy_for_evaluation


def test_episode_sets_reference_existing_files() -> None:
    for manifest_path in (ROOT / "configs" / "episode_sets").glob("*.yaml"):
        payload = yaml.safe_load(manifest_path.read_text())
        episodes = payload.get("episodes", [])
        assert episodes, manifest_path
        for episode in episodes:
            assert (ROOT / episode).exists(), f"{manifest_path}: {episode}"


def test_taxonomy_labels_trace_required_family() -> None:
    taxonomy = load_episode_taxonomy(ROOT / "configs" / "episode_taxonomy.yaml")
    labels = taxonomy_for_evaluation(
        {
            "problem_id": "native_dependency_bad_endpoint_frontend_cartservice",
            "expected_fault_class": "native_dependency_bad_endpoint",
        },
        taxonomy,
    )

    assert labels["diagnosis_category"] == "dependency_path_trace_centered"
    assert labels["difficulty"] == "causal_path"
    assert labels["trace_required"] is True


def test_aggregate_evaluations_groups_by_taxonomy() -> None:
    taxonomy = load_episode_taxonomy(ROOT / "configs" / "episode_taxonomy.yaml")
    aggregate = aggregate_evaluations(
        [
            {
                "problem_id": "native_service_port_mismatch_productcatalogservice",
                "agent_variant": "compact_one_shot",
                "agent_type": "benchmark",
                "model": "test",
                "diagnosis_correct": True,
                "action_correct": False,
                "expected_fault_class": "native_service_port_mismatch",
                "tool_calls_to_solution": 1,
            },
            {
                "problem_id": "native_bad_env_checkoutservice_email",
                "agent_variant": "compact_one_shot",
                "agent_type": "benchmark",
                "model": "test",
                "diagnosis_correct": False,
                "action_correct": False,
                "expected_fault_class": "native_bad_env",
                "tool_calls_to_solution": 2,
            },
        ],
        taxonomy=taxonomy,
    )

    categories = {row["key"]: row for row in aggregate["groups"]["diagnosis_category"]}
    assert categories["service_wiring_configuration"]["runs"] == 1
    assert categories["dependency_path_trace_centered"]["runs"] == 1
    trace_groups = {row["key"]: row for row in aggregate["groups"]["trace_required"]}
    assert trace_groups["trace_required"]["runs"] == 1
    assert trace_groups["trace_not_required"]["runs"] == 1


def test_dependency_family_partial_credit_aggregates_separately() -> None:
    taxonomy = load_episode_taxonomy(ROOT / "configs" / "episode_taxonomy.yaml")
    aggregate = aggregate_evaluations(
        [
            {
                "problem_id": "native_bad_env_checkoutservice_email",
                "agent_variant": "structured_compact",
                "agent_type": "benchmark",
                "model": "test",
                "diagnosis_correct": False,
                "diagnosis_family_correct": True,
                "action_correct": True,
                "expected_fault_class": "native_bad_env",
                "submitted_fault_class": "native_dependency_bad_endpoint",
                "expected_fault_family": "dependency_configuration_regression",
                "submitted_fault_family": "dependency_configuration_regression",
                "tool_calls_to_solution": 2,
            },
        ],
        taxonomy=taxonomy,
    )

    categories = {row["key"]: row for row in aggregate["groups"]["diagnosis_category"]}
    dependency = categories["dependency_path_trace_centered"]
    assert dependency["diagnosis_accuracy"] == 0.0
    assert dependency["diagnosis_family_accuracy"] == 1.0
