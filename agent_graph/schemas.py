from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class Hypothesis:
    id: str
    title: str
    suspected_service: str
    category: str
    confidence: float
    rationale: str
    validation_plan: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceItem:
    source: str
    name: str
    summary: str
    supports: List[str] = field(default_factory=list)
    contradicts: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ActionPlan:
    action: str
    target: str
    rationale: str
    expected_signal: str
    command: List[str] = field(default_factory=list)
    allowed: bool = True
    dry_run: bool = True
    executed: bool = False
    result: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VerificationResult:
    recovered: bool
    root_cause_mitigated: bool
    before_incident_detected: bool
    after_incident_detected: bool
    before_summary: str
    after_summary: str
    note: str = ""
    stages: Dict[str, Any] = field(default_factory=dict)
    samples: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class IncidentContext:
    timestamp_utc: str
    detection: Dict[str, Any]
    target_deployment: str
    namespace: str
    prom_url: str
    jaeger_url: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class IterationReport:
    iteration: int
    state_history: List[str]
    hypotheses: List[Dict[str, Any]]
    evidence: List[Dict[str, Any]]
    supported_hypothesis: Dict[str, Any]
    action: Dict[str, Any]
    verification: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgentReport:
    timestamp_utc: str
    mode: str
    incident: Dict[str, Any]
    iterations: List[Dict[str, Any]]
    final_state: str
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
