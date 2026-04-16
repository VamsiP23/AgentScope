from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from benchmarking.problem import ProblemSpec


EVIDENCE_PATTERN = re.compile(r"^(?P<tool>[a-z_]+)\((?P<service>[^)]*)\)$")


@dataclass
class RunEvaluation:
    problem_id: str
    status: str
    agent_type: str
    agent_variant: str
    model: str
    incident_detected: bool
    diagnosis_correct: bool
    action_correct: bool
    tool_calls_to_solution: int
    time_to_diagnosis_seconds: Optional[float]
    invalid_submit_count: int
    repeated_call_count: int
    evidence_coverage: float
    missing_required_evidence: List[str] = field(default_factory=list)
    submitted_root_cause: str = ""
    submitted_action: str = ""
    submitted_fault_class: str = ""
    expected_fault_class: str = ""
    submitted_affected_service: str = ""
    expected_affected_service: str = ""
    submitted_action_type: str = ""
    expected_action_types: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "status": self.status,
            "agent_type": self.agent_type,
            "agent_variant": self.agent_variant,
            "model": self.model,
            "incident_detected": self.incident_detected,
            "diagnosis_correct": self.diagnosis_correct,
            "action_correct": self.action_correct,
            "tool_calls_to_solution": self.tool_calls_to_solution,
            "time_to_diagnosis_seconds": self.time_to_diagnosis_seconds,
            "invalid_submit_count": self.invalid_submit_count,
            "repeated_call_count": self.repeated_call_count,
            "evidence_coverage": self.evidence_coverage,
            "missing_required_evidence": list(self.missing_required_evidence),
            "submitted_root_cause": self.submitted_root_cause,
            "submitted_action": self.submitted_action,
            "submitted_fault_class": self.submitted_fault_class,
            "expected_fault_class": self.expected_fault_class,
            "submitted_affected_service": self.submitted_affected_service,
            "expected_affected_service": self.expected_affected_service,
            "submitted_action_type": self.submitted_action_type,
            "expected_action_types": list(self.expected_action_types),
        }


def evaluate_agent_run(problem: ProblemSpec, agent_report: Dict[str, Any]) -> RunEvaluation:
    steps = list(agent_report.get("steps", []) or [])
    solution = dict(agent_report.get("solution", {}) or {})
    seeded_detection = dict(agent_report.get("seeded_detection", {}) or {})
    incident_detected = bool(seeded_detection.get("incident_detected", False))
    agent_type = str(agent_report.get("agent_type", "")).strip() or "unknown"
    agent_variant = str(agent_report.get("agent_variant", "")).strip() or "pure_react"
    model = str(agent_report.get("model", "")).strip()

    submitted_root_cause = str(solution.get("root_cause", "")).strip()
    submitted_action = str(solution.get("action_taken", "")).strip()
    submitted_fault_class = str(solution.get("fault_class", "")).strip()
    submitted_affected_service = str(solution.get("affected_service", "")).strip()
    submitted_action_type = str(solution.get("action_type", "")).strip()
    expected_fault_class = _expected_fault_class(problem)
    expected_affected_service = problem.target_service
    expected_action_types = _expected_action_types(problem)

    structured_diagnosis_present = bool(submitted_fault_class or submitted_affected_service)
    if structured_diagnosis_present:
        diagnosis_correct = (
            _normalize_label(submitted_fault_class) == _normalize_label(expected_fault_class)
            and _normalize_service(submitted_affected_service) == _normalize_service(expected_affected_service)
        )
    else:
        diagnosis_correct = _normalized_match(
            submitted_root_cause,
            problem.ground_truth.acceptable_root_causes,
        )

    if submitted_action_type:
        action_correct = _normalize_label(submitted_action_type) in {
            _normalize_label(action_type) for action_type in expected_action_types
        } and _action_targets_expected_service(submitted_action, submitted_affected_service, expected_affected_service)
    else:
        action_correct = _action_text_match(
            submitted_action,
            problem.ground_truth.acceptable_actions,
            expected_action_types,
            expected_affected_service,
        )

    submit_step = _first_successful_submit_step(steps)
    tool_calls_to_solution = len(
        [step for step in steps if step.get("tool_called") != "submit_solution"]
    )
    time_to_diagnosis_seconds: Optional[float] = None
    if submit_step is not None and steps:
        first_ts = _step_timestamp(steps[0])
        submit_ts = _step_timestamp(submit_step)
        if first_ts is not None and submit_ts is not None and submit_ts >= first_ts:
            time_to_diagnosis_seconds = round(submit_ts - first_ts, 3)

    invalid_submit_count = 0
    for step in steps:
        if step.get("tool_called") != "submit_solution":
            continue
        output = step.get("output", {}) or {}
        if not output.get("solution_logged") or output.get("error") or not output.get("evidence_valid", True):
            invalid_submit_count += 1

    repeated_call_count = _repeated_call_count(steps)
    evidence_coverage, missing = _evidence_coverage(problem, steps)

    return RunEvaluation(
        problem_id=problem.problem_id,
        status=problem.status,
        agent_type=agent_type,
        agent_variant=agent_variant,
        model=model,
        incident_detected=incident_detected,
        diagnosis_correct=diagnosis_correct,
        action_correct=action_correct,
        tool_calls_to_solution=tool_calls_to_solution,
        time_to_diagnosis_seconds=time_to_diagnosis_seconds,
        invalid_submit_count=invalid_submit_count,
        repeated_call_count=repeated_call_count,
        evidence_coverage=evidence_coverage,
        missing_required_evidence=missing,
        submitted_root_cause=submitted_root_cause,
        submitted_action=submitted_action,
        submitted_fault_class=submitted_fault_class,
        expected_fault_class=expected_fault_class,
        submitted_affected_service=submitted_affected_service,
        expected_affected_service=expected_affected_service,
        submitted_action_type=submitted_action_type,
        expected_action_types=expected_action_types,
    )


def _normalized_match(value: str, accepted: List[str]) -> bool:
    normalized = _normalize_text(value)
    if not normalized:
        return False
    return any(normalized == _normalize_text(candidate) for candidate in accepted)


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _normalize_service(value: str) -> str:
    normalized = _normalize_label(value)
    if normalized.startswith("deployment_"):
        normalized = normalized[len("deployment_") :]
    if normalized.startswith("service_"):
        normalized = normalized[len("service_") :]
    return normalized


def _expected_fault_class(problem: ProblemSpec) -> str:
    return problem.task_family or problem.category or problem.problem_id


def _expected_action_types(problem: ProblemSpec) -> List[str]:
    action_types: List[str] = []
    for action in problem.ground_truth.acceptable_actions:
        action_type = _action_type_from_text(action)
        if action_type and action_type not in action_types:
            action_types.append(action_type)
    return action_types or ["wait_and_monitor"]


def _action_type_from_text(value: str) -> str:
    text = _normalize_text(value)
    label = _normalize_label(value)
    if "patch_service_target_port" in label or ("targetport" in text and "service" in text):
        return "patch_service_target_port"
    if "patch_service_selector" in label or ("selector" in text and "service" in text):
        return "patch_service_selector"
    if "patch_resources_then_scale" in label:
        return "patch_resources_then_scale"
    if "patch_resources" in label or "patch resource" in text:
        return "patch_resources"
    if "scale_deployment" in label or text.startswith("scale deployment") or text.startswith("kubectl scale"):
        return "scale_deployment"
    if "rollout_undo" in label or "rollout undo" in text:
        return "rollout_undo"
    if "rollout_restart" in label or "rollout restart" in text:
        return "rollout_restart"
    if "restart_pod" in label or "delete pod" in text:
        return "restart_pod"
    if "wait_and_monitor" in label or "wait and monitor" in text or "monitor" == text:
        return "wait_and_monitor"
    return ""


def _action_text_match(
    submitted_action: str,
    accepted_actions: List[str],
    expected_action_types: List[str],
    expected_service: str,
) -> bool:
    if _normalized_match(submitted_action, accepted_actions):
        return True
    submitted_type = _action_type_from_text(submitted_action)
    if not submitted_type:
        return False
    if _normalize_label(submitted_type) not in {_normalize_label(action_type) for action_type in expected_action_types}:
        return False
    normalized_action = _normalize_text(submitted_action)
    return _normalize_service(expected_service) in _normalize_service(normalized_action)


def _action_targets_expected_service(submitted_action: str, submitted_affected_service: str, expected_service: str) -> bool:
    if submitted_affected_service:
        return _normalize_service(submitted_affected_service) == _normalize_service(expected_service)
    return _normalize_service(expected_service) in _normalize_service(submitted_action)


def _first_successful_submit_step(steps: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for step in steps:
        if step.get("tool_called") != "submit_solution":
            continue
        output = step.get("output", {}) or {}
        if output.get("solution_logged") and not output.get("error") and output.get("evidence_valid", True):
            return step
    return None


def _step_timestamp(step: Dict[str, Any]) -> Optional[float]:
    value = step.get("timestamp")
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _repeated_call_count(steps: List[Dict[str, Any]]) -> int:
    repeats = 0
    prior: Optional[Tuple[str, str]] = None
    for step in steps:
        tool = str(step.get("tool_called", ""))
        service = str((step.get("inputs", {}) or {}).get("service", "")).strip()
        current = (tool, service)
        if tool == "submit_solution":
            continue
        if prior == current:
            repeats += 1
        prior = current
    return repeats


def _evidence_coverage(problem: ProblemSpec, steps: List[Dict[str, Any]]) -> Tuple[float, List[str]]:
    required = list(problem.ground_truth.required_evidence)
    if not required:
        return 1.0, []

    seen = set()
    for step in steps:
        tool = str(step.get("tool_called", "")).strip()
        if tool == "submit_solution":
            continue
        service = str((step.get("inputs", {}) or {}).get("service", "")).strip()
        seen.add(f"{tool}({service})")

    missing = [item for item in required if item not in seen]
    coverage = (len(required) - len(missing)) / len(required)
    return round(coverage, 3), missing
