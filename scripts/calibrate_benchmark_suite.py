#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarking.problem import BenchmarkSuite, ProblemSpec, load_benchmark_suite


ARTIFACT_RE = re.compile(r"Artifacts:\s*(?P<path>.+)$")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Calibrate benchmark experiments until detector reliability is stable.")
    parser.add_argument(
        "--suite",
        default=str(ROOT / "benchmark_suite.yaml"),
        help="Benchmark suite YAML file.",
    )
    parser.add_argument(
        "--status",
        default="candidate",
        help="Only calibrate experiments with this current status.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of runs per experiment.",
    )
    parser.add_argument(
        "--skip-startup",
        action="store_true",
        help="Pass --skip-startup through to run_experiment.py.",
    )
    parser.add_argument(
        "--promote-ready",
        action="store_true",
        help="Update the suite file to mark experiments ready when reliability is 1.0 for all runs.",
    )
    parser.add_argument(
        "--problems",
        nargs="*",
        default=[],
        help="Optional explicit benchmark problem IDs to calibrate.",
    )
    parser.add_argument(
        "--out-file",
        default="",
        help="Optional file to write the calibration summary JSON.",
    )
    return parser


def run_experiment(problem: ProblemSpec, skip_startup: bool) -> Dict[str, Any]:
    if problem.experiment_file is None:
        raise RuntimeError(f"problem {problem.problem_id} has no experiment file")

    cmd = [
        "python3",
        "./scripts/run_experiment.py",
        str(problem.experiment_file),
    ]
    if skip_startup:
        cmd.append("--skip-startup")

    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    combined = "\n".join(part for part in [proc.stdout, proc.stderr] if part)
    artifact_dir = extract_artifact_dir(combined)
    evaluation = read_json(artifact_dir / "evaluation.json") if artifact_dir else {}
    agent_report = read_json(artifact_dir / "agent_report.json") if artifact_dir else {}
    return {
        "command": cmd,
        "returncode": proc.returncode,
        "artifact_dir": str(artifact_dir) if artifact_dir else "",
        "evaluation": evaluation,
        "agent_report": {
            "agent_variant": agent_report.get("agent_variant", ""),
            "model": agent_report.get("model", ""),
            "error": agent_report.get("error"),
            "solution": agent_report.get("solution", {}),
        },
        "stdout_tail": tail_text(proc.stdout),
        "stderr_tail": tail_text(proc.stderr),
    }


def extract_artifact_dir(output: str) -> Path | None:
    for line in reversed(output.splitlines()):
        match = ARTIFACT_RE.search(line.strip())
        if match:
            candidate = Path(match.group("path").strip())
            if candidate.exists():
                return candidate.resolve()
    return None


def tail_text(value: str, line_limit: int = 20) -> str:
    lines = [line for line in value.splitlines() if line.strip()]
    return "\n".join(lines[-line_limit:])


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def should_include(problem: ProblemSpec, requested_status: str, requested_ids: List[str]) -> bool:
    if requested_ids and problem.problem_id not in requested_ids:
        return False
    return problem.status == requested_status


def summarize_runs(problem: ProblemSpec, run_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    incident_hits = 0
    completed = 0
    diagnosis_hits = 0
    action_hits = 0
    artifact_dirs: List[str] = []

    for run in run_results:
        evaluation = run.get("evaluation", {}) or {}
        if run.get("returncode", 1) == 0:
            completed += 1
        if evaluation.get("incident_detected"):
            incident_hits += 1
        if evaluation.get("diagnosis_correct"):
            diagnosis_hits += 1
        if evaluation.get("action_correct"):
            action_hits += 1
        artifact_dir = str(run.get("artifact_dir", "")).strip()
        if artifact_dir:
            artifact_dirs.append(artifact_dir)

    total = max(1, len(run_results))
    return {
        "problem_id": problem.problem_id,
        "status_before": problem.status,
        "runs_requested": len(run_results),
        "runs_completed": completed,
        "detector_reliability": round(incident_hits / total, 3),
        "diagnosis_accuracy": round(diagnosis_hits / total, 3),
        "action_accuracy": round(action_hits / total, 3),
        "promote_to_ready": incident_hits == len(run_results) and len(run_results) > 0,
        "artifact_dirs": artifact_dirs,
        "runs": run_results,
    }


def update_suite_statuses(suite_path: Path, promotions: Dict[str, str]) -> None:
    payload = yaml.safe_load(suite_path.read_text())
    if not isinstance(payload, dict):
        raise RuntimeError(f"benchmark suite must parse to a mapping: {suite_path}")
    for section in ("experiments", "stretch_experiments"):
        for item in payload.get(section, []) or []:
            problem_id = str((item or {}).get("id", ""))
            if problem_id in promotions:
                item["status"] = promotions[problem_id]
    suite_path.write_text(yaml.safe_dump(payload, sort_keys=False))


def main() -> int:
    args = build_parser().parse_args()
    suite_path = Path(args.suite).resolve()
    suite: BenchmarkSuite = load_benchmark_suite(suite_path)

    candidates = [problem for problem in suite.problems if should_include(problem, args.status, list(args.problems))]
    results: List[Dict[str, Any]] = []
    promotions: Dict[str, str] = {}

    for problem in candidates:
        run_results: List[Dict[str, Any]] = []
        for _ in range(args.runs):
            run_results.append(
                run_experiment(
                    problem,
                    skip_startup=bool(args.skip_startup),
                )
            )
        summary = summarize_runs(problem, run_results)
        results.append(summary)
        if args.promote_ready and summary["promote_to_ready"]:
            promotions[problem.problem_id] = "ready"

    if promotions:
        update_suite_statuses(suite_path, promotions)

    payload = {
        "suite": str(suite_path),
        "agent_variant": "pure_react",
        "runs_per_problem": args.runs,
        "promotions": promotions,
        "results": results,
    }
    rendered = json.dumps(payload, indent=2)
    if args.out_file:
        out_path = Path(args.out_file).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered)
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
