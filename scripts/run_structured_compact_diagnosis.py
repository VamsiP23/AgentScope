#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_graph.reasoning.llm import make_json_client
from agent_graph.structured_compact_agent import infer_problem_id, run_structured_compact_diagnosis
from benchmarking.evaluator import evaluate_agent_run
from benchmarking.problem import load_benchmark_suite
from benchmarking.replay import ReplayDataset


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run bounded structured diagnosis over compact replay evidence.")
    parser.add_argument("--replay-dataset", required=True)
    parser.add_argument("--benchmark-suite", default=str(ROOT / "benchmark_suite.yaml"))
    parser.add_argument("--problem-id", default="")
    parser.add_argument("--provider", default="ollama")
    parser.add_argument("--model", default="")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--max-evidence-records", type=int, default=8)
    args = parser.parse_args()

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "agent_report.json"
    evaluation_path = out_dir / "evaluation.json"
    error_path = out_dir / "error.json"

    dataset_path = Path(args.replay_dataset).resolve()
    dataset = ReplayDataset.load(dataset_path)
    problem_id = args.problem_id or infer_problem_id(dataset_path, dataset)
    suite = load_benchmark_suite(Path(args.benchmark_suite))
    problem = suite.find_problem_by_id(problem_id)
    if problem is None:
        raise RuntimeError(f"unable to resolve problem id {problem_id}")

    client = make_json_client(provider=args.provider, model=args.model or None)
    try:
        result = run_structured_compact_diagnosis(
            client=client,
            dataset=dataset,
            max_evidence_records=args.max_evidence_records,
        )
    except Exception as exc:
        payload = {
            "timestamp_utc": utc_now(),
            "provider": args.provider,
            "model": client.model,
            "replay_dataset": str(dataset_path),
            "problem_id": problem_id,
            "error": str(exc),
        }
        error_path.write_text(json.dumps(payload, indent=2))
        print(json.dumps(payload, indent=2))
        return 2

    report = {
        "agent_type": "benchmark",
        "timestamp_utc": utc_now(),
        "provider": args.provider,
        "model": client.model,
        "agent_variant": "structured_compact",
        "backend": "replay",
        "diagnosis_only": True,
        "evidence_view": "compact",
        "replay_dataset": str(dataset_path),
        "problem": problem.to_dict(),
        "seeded_detection": {},
        "guardrail_events": [],
        "steps": result["steps"],
        "structured_trace": {
            "triage": result["triage"],
            "candidate_analysis": result["analysis"],
        },
        "solution": result["solution"],
        "verification": {},
        "error": None,
    }
    report_path.write_text(json.dumps(report, indent=2))
    evaluation = evaluate_agent_run(problem, report).to_dict()
    evaluation_path.write_text(json.dumps(evaluation, indent=2))
    print(
        json.dumps(
            {
                "agent_report": str(report_path),
                "evaluation": str(evaluation_path),
                "evaluation_summary": evaluation,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
