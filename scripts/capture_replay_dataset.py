#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def main() -> int:
    p = argparse.ArgumentParser(description="Capture a replayable benchmark dataset from a live run artifact directory.")
    p.add_argument("run_dir", help="Experiment run directory containing agent_report.json and aci_run_log.jsonl")
    p.add_argument("--out-file", default="", help="Optional output dataset path")
    args = p.parse_args()

    run_dir = Path(args.run_dir).resolve()
    report = load_json(run_dir / "agent_report.json")
    aci_rows = load_jsonl(run_dir / "aci_run_log.jsonl")
    detection = load_json(run_dir / "detector_runs" / "latest_detection.json")

    out_path = Path(args.out_file).resolve() if args.out_file else (run_dir / "replay_dataset.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "metadata": {
            "source_run_dir": str(run_dir),
            "captured_at_utc": str((report or {}).get("timestamp_utc", "")),
            "namespace": str((report or {}).get("namespace", "default")),
            "target_deployment": str((report or {}).get("target_deployment", "")),
            "problem_description": str((report or {}).get("problem_description", "")),
            "problem": dict((report or {}).get("problem", {}) or {}),
        },
        "initial_context": {
            "summary": str((detection or {}).get("summary", "")),
            "incident_detected": bool((detection or {}).get("incident_detected", False)),
            "suspicious_services": list((detection or {}).get("suspicious_services", []) or []),
            "critical_findings": list((detection or {}).get("findings", []) or []),
        },
        "calls": aci_rows,
    }
    out_path.write_text(json.dumps(payload, indent=2))
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
