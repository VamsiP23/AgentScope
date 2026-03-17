from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class DetectorFinding:
    name: str
    triggered: bool
    severity: str
    reason: str
    service: str = ""
    value: float | int | str = ""
    threshold: float | int | str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DetectionConfig:
    namespace: str = "default"
    prom_url: str = "http://localhost:9090"
    window: str = "1m"
    target_deployment: str = ""
    error_ratio_threshold: float = 0.10
    service_error_rps_threshold: float = 0.50
    min_total_rps: float = 0.10
    restart_count_threshold: int = 1
    out_file: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DetectionReport:
    timestamp_utc: str
    config: Dict[str, Any]
    incident_detected: bool
    suspicious_services: List[str]
    findings: List[Dict[str, Any]]
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
