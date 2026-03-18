from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from detectors.rules import DetectorRunner
from detectors.schemas import DetectionConfig, DetectionReport
from detectors.utils import utc_now


PRIMARY_DETECTORS = {"error_ratio", "service_error_rate", "deployment_availability"}


def build_report(config: DetectionConfig) -> DetectionReport:
    findings = DetectorRunner(config).run()
    fired = [f for f in findings if f.triggered]
    primary_fired = [f for f in fired if f.name in PRIMARY_DETECTORS]
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

    def write_report(self, report: DetectionReport) -> None:
        payload = json.dumps(report.to_dict(), indent=2)
        self.latest_path.write_text(payload)
        with self.jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(report.to_dict()) + "\n")

    def run_forever(self) -> int:
        while True:
            report = build_report(self.config)
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
