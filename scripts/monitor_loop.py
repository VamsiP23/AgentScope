#!/usr/bin/env python3
"""Poll the detectors repeatedly and write JSON artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from detectors.monitor import MonitorLoop
from detectors.schemas import DetectionConfig
from detectors.utils import require_binary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run the detection loop continuously and write JSON outputs.")
    p.add_argument("--namespace", default="default")
    p.add_argument("--prom-url", default="http://localhost:9090")
    p.add_argument("--window", default="1m")
    p.add_argument("--target-deployment", default="")
    p.add_argument("--error-ratio-threshold", type=float, default=0.10)
    p.add_argument("--service-error-rps-threshold", type=float, default=0.50)
    p.add_argument("--service-latency-threshold-ms", type=float, default=1000.0)
    p.add_argument("--min-total-rps", type=float, default=0.10)
    p.add_argument("--restart-count-threshold", type=int, default=1)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--interval-seconds", type=int, default=10)
    return p


def main() -> int:
    args = build_parser().parse_args()
    require_binary("kubectl")
    config = DetectionConfig(
        namespace=args.namespace,
        prom_url=args.prom_url,
        window=args.window,
        target_deployment=args.target_deployment,
        error_ratio_threshold=args.error_ratio_threshold,
        service_error_rps_threshold=args.service_error_rps_threshold,
        service_latency_threshold_ms=args.service_latency_threshold_ms,
        min_total_rps=args.min_total_rps,
        restart_count_threshold=args.restart_count_threshold,
    )
    loop = MonitorLoop(config, args.out_dir, args.interval_seconds)
    return loop.run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
