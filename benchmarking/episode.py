from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import json


@dataclass
class EpisodeTransition:
    trigger_type: str
    trigger_value: str
    target_phase: int
    label: str = ""
    threshold: int = 0


@dataclass
class EpisodePhase:
    phase_id: int
    label: str
    tool_responses: Dict[str, Any] = field(default_factory=dict)
    observability: Dict[str, Any] = field(default_factory=dict)
    transitions: List[EpisodeTransition] = field(default_factory=list)


@dataclass
class EpisodeGroundTruth:
    root_cause: str
    root_cause_service: str
    fault_class: str
    correct_actions: List[Dict[str, Any]] = field(default_factory=list)
    acceptable_actions: List[Dict[str, Any]] = field(default_factory=list)
    incorrect_actions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class EpisodeTelemetryContract:
    required_present: List[str] = field(default_factory=list)
    required_nonzero: List[str] = field(default_factory=list)


@dataclass
class EpisodeScoring:
    max_steps: int = 12
    diagnosis_weight: float = 0.5
    action_correctness_weight: float = 0.3
    step_economy_weight: float = 0.2
    step_economy_baseline: int = 6


@dataclass
class EpisodeProvenance:
    source_run_dir: str
    captured_from_live_run: bool = True
    capture_timestamp_utc: str = ""


@dataclass
class BenchmarkEpisode:
    task_id: str
    family: str
    scenario: str
    split: str
    difficulty: str
    fault_spec: Dict[str, Any]
    initial_context: str
    phases: List[EpisodePhase]
    ground_truth: EpisodeGroundTruth
    telemetry_contract: EpisodeTelemetryContract
    scoring: EpisodeScoring
    provenance: EpisodeProvenance

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: Path) -> Dict[str, Any]:
        return json.loads(path.read_text())
