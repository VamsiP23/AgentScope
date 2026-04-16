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
    service_latency_threshold_ms: float = 1000.0
    latency_consecutive_required: int = 2
    service_error_consecutive_required: int = 1
    min_total_rps: float = 0.10
    restart_count_threshold: int = 1
    primary_detectors: List[str] = field(
        default_factory=lambda: [
            "error_ratio",
            "service_error_rate",
            "service_latency",
            "deployment_availability",
            "service_endpoints",
            "service_port_alignment",
            "native_stress_job",
        ]
    )
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
