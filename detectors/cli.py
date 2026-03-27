from __future__ import annotations

import argparse
import json
from pathlib import Path

from detectors.rules import DetectorRunner
from detectors.schemas import DetectionConfig, DetectionReport
from detectors.utils import require_binary, utc_now


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run metric and cluster-health detectors and print a structured incident report."
    )
    p.add_argument("--namespace", default="default")
    p.add_argument("--prom-url", default="http://localhost:9090")
    p.add_argument("--window", default="1m")
    p.add_argument("--target-deployment", default="")
    p.add_argument("--error-ratio-threshold", type=float, default=0.10)
    p.add_argument("--service-error-rps-threshold", type=float, default=0.50)
    p.add_argument("--service-latency-threshold-ms", type=float, default=1000.0)
    p.add_argument("--min-total-rps", type=float, default=0.10)
    p.add_argument("--restart-count-threshold", type=int, default=1)
    p.add_argument("--out-file", default="")
    return p


def main() -> int:
    args = build_parser().parse_args()
    require_binary("kubectl")

    config = DetectionConfig(**vars(args))
    findings = DetectorRunner(config).run()
    fired = [f for f in findings if f.triggered]
    primary_detector_names = {"error_ratio", "service_error_rate", "service_latency", "deployment_availability"}
    primary_fired = [f for f in fired if f.name in primary_detector_names]

    suspicious_services = sorted({f.service for f in fired if f.service})
    if primary_fired:
        summary = "; ".join(f.reason for f in primary_fired)
    elif fired:
        summary = "supporting signals only: " + "; ".join(f.reason for f in fired)
    else:
        summary = "no detector triggered"

    report = DetectionReport(
        timestamp_utc=utc_now(),
        config=config.to_dict(),
        incident_detected=bool(primary_fired),
        suspicious_services=suspicious_services,
        findings=[f.to_dict() for f in findings],
        summary=summary,
    )

    payload = json.dumps(report.to_dict(), indent=2)
    if config.out_file:
        path = Path(config.out_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload)
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
