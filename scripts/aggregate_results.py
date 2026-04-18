#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarking.results import aggregate_evaluations, load_episode_taxonomy, load_run_evaluations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate benchmark evaluation JSON files.")
    parser.add_argument("--run-root", required=True, help="Directory containing per-episode run folders.")
    parser.add_argument("--taxonomy", default=str(ROOT / "configs" / "episode_taxonomy.yaml"))
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    return parser


def markdown_table(title: str, rows: List[Dict[str, Any]]) -> str:
    lines = [f"## {title}", ""]
    if not rows:
        lines.extend(["No rows.", ""])
        return "\n".join(lines)
    columns = [
        "key",
        "runs",
        "diagnosis_accuracy",
        "diagnosis_family_accuracy",
        "action_accuracy",
        "valid_submission_rate",
        "avg_tool_calls_to_solution",
        "avg_time_to_diagnosis_seconds",
    ]
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("| " + " | ".join("---" for _ in columns) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(column, "")) for column in columns) + " |")
    lines.append("")
    return "\n".join(lines)


def render_markdown(aggregate: Dict[str, Any]) -> str:
    lines = [
        "# Benchmark Aggregate Results",
        "",
        f"- Runs: {aggregate.get('runs', 0)}",
        "",
    ]
    groups = dict(aggregate.get("groups", {}) or {})
    lines.append(markdown_table("Diagnosis Category", list(groups.get("diagnosis_category", []) or [])))
    lines.append(markdown_table("Difficulty", list(groups.get("difficulty", []) or [])))
    lines.append(markdown_table("Trace Required", list(groups.get("trace_required", []) or [])))
    lines.append(markdown_table("Fault Family", list(groups.get("fault_family", []) or [])))
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = build_parser().parse_args()
    run_root = Path(args.run_root).resolve()
    taxonomy = load_episode_taxonomy(Path(args.taxonomy)) if args.taxonomy else {}
    evaluations = load_run_evaluations(run_root)
    aggregate = aggregate_evaluations(evaluations, taxonomy=taxonomy)

    out_json = Path(args.out_json) if args.out_json else run_root / "aggregate_results.json"
    out_md = Path(args.out_md) if args.out_md else run_root / "aggregate_results.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(aggregate, indent=2))
    out_md.write_text(render_markdown(aggregate))
    print(json.dumps({"evaluations": len(evaluations), "aggregate_json": str(out_json), "aggregate_md": str(out_md)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
