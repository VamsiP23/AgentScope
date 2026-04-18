from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarking.evaluator import evaluate_agent_run
from benchmarking.problem import GroundTruth, ProblemSpec


def test_dependency_family_partial_credit_does_not_change_exact_score() -> None:
    problem = ProblemSpec(
        problem_id="native_bad_env_checkoutservice_email",
        status="candidate",
        category="dependency_trace",
        experiment_file=None,
        target_service="checkoutservice",
        detector_gate={},
        task_family="native_bad_env",
        ground_truth=GroundTruth(
            acceptable_root_causes=["checkoutservice bad env"],
            acceptable_actions=["kubectl rollout undo deployment/checkoutservice"],
            required_evidence=[],
        ),
    )
    report = {
        "agent_type": "benchmark",
        "agent_variant": "structured_compact",
        "model": "fake",
        "solution": {
            "root_cause": "Dependency endpoint regression",
            "fault_class": "native_dependency_bad_endpoint",
            "affected_service": "checkoutservice",
            "action_type": "rollout_undo",
            "action_taken": "rollout undo checkoutservice",
        },
        "steps": [
            {
                "tool_called": "submit_solution",
                "timestamp": 1.0,
                "output": {"solution_logged": True, "evidence_valid": True},
            }
        ],
    }

    evaluation = evaluate_agent_run(problem, report).to_dict()

    assert evaluation["diagnosis_correct"] is False
    assert evaluation["diagnosis_family_correct"] is True
    assert evaluation["expected_fault_family"] == "dependency_configuration_regression"
    assert evaluation["submitted_fault_family"] == "dependency_configuration_regression"
    assert evaluation["action_correct"] is True
