#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarking.results import aggregate_evaluations, load_run_evaluations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate AgentScope benchmark evaluation files.")
    parser.add_argument(
        "--run-root",
        default=str(ROOT / "experiment_runs"),
        help="Directory containing per-run folders with evaluation.json artifacts.",
    )
    parser.add_argument(
        "--out-file",
        default="",
        help="Optional file to write the aggregate JSON summary.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    run_root = Path(args.run_root).resolve()
    evaluations = load_run_evaluations(run_root)
    payload = aggregate_evaluations(evaluations)
    rendered = json.dumps(payload, indent=2)
    if args.out_file:
        out_path = Path(args.out_file).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered)
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
