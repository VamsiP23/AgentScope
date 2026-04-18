from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class GroundTruth:
    acceptable_root_causes: List[str] = field(default_factory=list)
    acceptable_actions: List[str] = field(default_factory=list)
    required_evidence: List[str] = field(default_factory=list)
    traces_required: bool = False


@dataclass
class TelemetryContract:
    required_validation_checks: List[str] = field(default_factory=list)
    required_services: List[str] = field(default_factory=list)
    fail_open: bool = False
    notes: str = ""


@dataclass
class ProblemSpec:
    problem_id: str
    status: str
    category: str
    experiment_file: Optional[Path]
    target_service: str
    detector_gate: Dict[str, Any]
    ground_truth: GroundTruth
    task_family: str = ""
    scenario: str = ""
    entry_service: str = "frontend"
    telemetry_contract: TelemetryContract = field(default_factory=TelemetryContract)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.problem_id,
            "status": self.status,
            "category": self.category,
            "experiment_file": str(self.experiment_file) if self.experiment_file else "",
            "target_service": self.target_service,
            "detector_gate": dict(self.detector_gate),
            "ground_truth": {
                "acceptable_root_causes": list(self.ground_truth.acceptable_root_causes),
                "acceptable_actions": list(self.ground_truth.acceptable_actions),
                "required_evidence": list(self.ground_truth.required_evidence),
                "traces_required": self.ground_truth.traces_required,
            },
            "task_family": self.task_family,
            "scenario": self.scenario,
            "entry_service": self.entry_service,
            "telemetry_contract": {
                "required_validation_checks": list(self.telemetry_contract.required_validation_checks),
                "required_services": list(self.telemetry_contract.required_services),
                "fail_open": self.telemetry_contract.fail_open,
                "notes": self.telemetry_contract.notes,
            },
            "notes": self.notes,
        }


@dataclass
class BenchmarkSuite:
    path: Path
    version: int
    name: str
    goal: str
    problems: List[ProblemSpec] = field(default_factory=list)
    stretch_problems: List[ProblemSpec] = field(default_factory=list)

    def find_problem_by_experiment(self, experiment_path: Path) -> Optional[ProblemSpec]:
        target = experiment_path.resolve()
        for problem in [*self.problems, *self.stretch_problems]:
            if problem.experiment_file and problem.experiment_file.resolve() == target:
                return problem
        return None

    def find_problem_by_id(self, problem_id: str) -> Optional[ProblemSpec]:
        for problem in [*self.problems, *self.stretch_problems]:
            if problem.problem_id == problem_id:
                return problem
        return None


def load_benchmark_suite(path: Path) -> BenchmarkSuite:
    suite_path = path.resolve()
    payload = yaml.safe_load(suite_path.read_text())
    if not isinstance(payload, dict):
        raise RuntimeError(f"benchmark suite must parse to a mapping: {path}")

    def parse_problem(item: Dict[str, Any]) -> ProblemSpec:
        experiment_value = item.get("experiment_file")
        experiment_path = None
        if experiment_value:
            raw_experiment_path = Path(str(experiment_value))
            if not raw_experiment_path.is_absolute():
                raw_experiment_path = suite_path.parent / raw_experiment_path
            experiment_path = raw_experiment_path.resolve()
        ground_truth_raw = item.get("ground_truth", {}) or {}
        ground_truth = GroundTruth(
            acceptable_root_causes=[str(v) for v in ground_truth_raw.get("acceptable_root_causes", []) or []],
            acceptable_actions=[str(v) for v in ground_truth_raw.get("acceptable_actions", []) or []],
            required_evidence=[str(v) for v in ground_truth_raw.get("required_evidence", []) or []],
            traces_required=bool(ground_truth_raw.get("traces_required", False)),
        )
        telemetry_raw = item.get("telemetry_contract", {}) or {}
        telemetry_contract = TelemetryContract(
            required_validation_checks=[str(v) for v in telemetry_raw.get("required_validation_checks", []) or []],
            required_services=[str(v) for v in telemetry_raw.get("required_services", []) or []],
            fail_open=bool(telemetry_raw.get("fail_open", False)),
            notes=str(telemetry_raw.get("notes", "")),
        )
        return ProblemSpec(
            problem_id=str(item.get("id", "")),
            status=str(item.get("status", "candidate")),
            category=str(item.get("category", "")),
            experiment_file=experiment_path,
            target_service=str(item.get("target_service", "")),
            detector_gate=dict(item.get("detector_gate", {}) or {}),
            ground_truth=ground_truth,
            task_family=str(item.get("task_family", "")),
            scenario=str(item.get("scenario", "")),
            entry_service=str(item.get("entry_service", "frontend") or "frontend"),
            telemetry_contract=telemetry_contract,
            notes=str(item.get("notes", "")),
        )

    problems = [parse_problem(item) for item in payload.get("experiments", []) or []]
    stretch = [parse_problem(item) for item in payload.get("stretch_experiments", []) or []]
    return BenchmarkSuite(
        path=suite_path,
        version=int(payload.get("version", 1) or 1),
        name=str(payload.get("name", path.stem)),
        goal=str(payload.get("goal", "")),
        problems=problems,
        stretch_problems=stretch,
    )


def resolve_problem_for_experiment(experiment_path: Path, suite_path: Path) -> Optional[ProblemSpec]:
    if not suite_path.exists():
        return None
    suite = load_benchmark_suite(suite_path)
    return suite.find_problem_by_experiment(experiment_path)
