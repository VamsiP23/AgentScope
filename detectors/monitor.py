from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Optional

from detectors.rules import DetectorRunner
from detectors.schemas import DetectionConfig, DetectionReport
from detectors.utils import utc_now

DEFAULT_PRIMARY_DETECTORS = {
    "error_ratio",
    "service_error_rate",
    "service_latency",
    "deployment_availability",
    "service_endpoints",
    "service_port_alignment",
    "native_stress_job",
}


def build_report(config: DetectionConfig) -> DetectionReport:
    findings = DetectorRunner(config).run()
    fired = [f for f in findings if f.triggered]
    primary_detectors = set(config.primary_detectors or DEFAULT_PRIMARY_DETECTORS)
    primary_fired = [f for f in fired if f.name in primary_detectors]
    suspicious_services = sorted({f.service for f in fired if f.service})
    if primary_fired:
        summary = "; ".join(f.reason for f in primary_fired)
    elif fired:
        summary = "supporting signals only: " + "; ".join(f.reason for f in fired)
    else:
        summary = "no detector triggered"
    return DetectionReport(
        timestamp_utc=utc_now(),
        config=config.to_dict(),
        incident_detected=bool(primary_fired),
        suspicious_services=suspicious_services,
        findings=[f.to_dict() for f in findings],
        summary=summary,
    )


class MonitorLoop:
    def __init__(self, config: DetectionConfig, out_dir: str, interval_seconds: int = 10) -> None:
        self.config = config
        self.out_dir = Path(out_dir)
        self.interval_seconds = interval_seconds
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.out_dir / "detections.jsonl"
        self.latest_path = self.out_dir / "latest_detection.json"
        self._last_incident_state: Optional[bool] = None
        self._last_summary: str = ""
        self._latency_consecutive_count = 0
        self._service_error_consecutive_count = 0

    def _stabilize_report(self, report: DetectionReport) -> DetectionReport:
        primary_detectors = set(self.config.primary_detectors or DEFAULT_PRIMARY_DETECTORS)
        latency_fired = [item for item in report.findings if item.get("name") == "service_latency" and item.get("triggered")]
        service_error_fired = [
            item for item in report.findings if item.get("name") == "service_error_rate" and item.get("triggered")
        ]
        other_primary_fired = [
            item
            for item in report.findings
            if item.get("triggered") and item.get("name") in primary_detectors and item.get("name") != "service_latency"
        ]

        if latency_fired:
            self._latency_consecutive_count += 1
        else:
            self._latency_consecutive_count = 0

        if service_error_fired:
            self._service_error_consecutive_count += 1
        else:
            self._service_error_consecutive_count = 0

        required = max(1, int(self.config.latency_consecutive_required or 1))
        if (
            "service_latency" in primary_detectors
            and latency_fired
            and not other_primary_fired
            and self._latency_consecutive_count < required
        ):
            latency_reason = latency_fired[0].get("reason", "latency threshold exceeded")
            return replace(
                report,
                incident_detected=False,
                suspicious_services=[],
                summary=(
                    f"supporting signals only: {latency_reason} "
                    f"(awaiting consecutive confirmation {self._latency_consecutive_count}/{required})"
                ),
            )

        error_required = max(1, int(self.config.service_error_consecutive_required or 1))
        if (
            "service_error_rate" in primary_detectors
            and service_error_fired
            and not [item for item in other_primary_fired if item.get("name") != "service_error_rate"]
            and self._service_error_consecutive_count < error_required
        ):
            error_reason = service_error_fired[0].get("reason", "service error threshold exceeded")
            return replace(
                report,
                incident_detected=False,
                suspicious_services=[],
                summary=(
                    f"supporting signals only: {error_reason} "
                    f"(awaiting consecutive confirmation {self._service_error_consecutive_count}/{error_required})"
                ),
            )
        return report

    def write_report(self, report: DetectionReport) -> None:
        payload = json.dumps(report.to_dict(), indent=2)
        self.latest_path.write_text(payload)
        with self.jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(report.to_dict()) + "\n")

    def run_forever(self) -> int:
        while True:
            try:
                report = self._stabilize_report(build_report(self.config))
            except Exception as exc:
                print(f"[{utc_now()}] detector error: {exc}", flush=True)
                time.sleep(self.interval_seconds)
                continue
            self.write_report(report)
            if self._last_incident_state is None:
                print(
                    f"[{report.timestamp_utc}] detector initialized: incident_detected={report.incident_detected}; "
                    f"{report.summary}",
                    flush=True,
                )
            elif report.incident_detected != self._last_incident_state:
                state = "incident_detected" if report.incident_detected else "incident_cleared"
                print(f"[{report.timestamp_utc}] detector state change: {state}; {report.summary}", flush=True)
            elif report.incident_detected and report.summary != self._last_summary:
                print(f"[{report.timestamp_utc}] detector update: {report.summary}", flush=True)

            self._last_incident_state = report.incident_detected
            self._last_summary = report.summary
            time.sleep(self.interval_seconds)
