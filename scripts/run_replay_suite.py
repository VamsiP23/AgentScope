#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarking.results import aggregate_evaluations, load_episode_taxonomy, load_run_evaluations


VARIANT_TO_COMMAND = {
    "compact_one_shot": "run_compact_diagnosis.py",
    "structured_compact": "run_structured_compact_diagnosis.py",
    "generic_react": "run_benchmark_agent.py",
    "bounded_react": "run_benchmark_agent.py",
    "diagnostic": "run_benchmark_agent.py",
}


def utc_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def infer_problem_id(dataset_path: Path) -> str:
    task_id = dataset_path.stem
    return re.sub(r"_\d{3}$", "", task_id)


def load_episode_set(path: Path) -> Dict[str, Any]:
    payload = yaml.safe_load(path.read_text())
    if not isinstance(payload, dict):
        raise RuntimeError(f"episode set must parse to a mapping: {path}")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a replay benchmark suite over a committed episode set.")
    parser.add_argument(
        "--episode-set",
        default=str(ROOT / "configs" / "episode_sets" / "native_50.yaml"),
        help="YAML manifest listing replay episodes to evaluate.",
    )
    parser.add_argument(
        "--variant",
        required=True,
        choices=sorted(VARIANT_TO_COMMAND),
        help="Benchmark variant to run.",
    )
    parser.add_argument(
        "--benchmark-suite",
        default=str(ROOT / "benchmark_suite.yaml"),
        help="Benchmark suite YAML used for scoring and problem metadata.",
    )
    parser.add_argument("--provider", default="anthropic")
    parser.add_argument("--model", default="")
    parser.add_argument(
        "--out-root",
        default="",
        help="Optional explicit output directory. Defaults to results/replay_runs/<variant>_<timestamp>/",
    )
    parser.add_argument("--limit", type=int, default=0, help="Optional cap on the number of episodes to run.")
    parser.add_argument(
        "--include",
        default="",
        help="Optional substring filter on episode path or problem id.",
    )
    parser.add_argument("--max-steps", type=int, default=35, help="Step budget for replay agents.")
    parser.add_argument(
        "--max-evidence-records",
        type=int,
        default=8,
        help="Compact evidence budget for compact variants.",
    )
    return parser


def build_episode_command(
    *,
    variant: str,
    dataset_path: Path,
    out_dir: Path,
    benchmark_suite: Path,
    provider: str,
    model: str,
    max_steps: int,
    max_evidence_records: int,
) -> List[str]:
    command = ["python3", str(ROOT / "scripts" / VARIANT_TO_COMMAND[variant])]
    if variant in {"compact_one_shot", "structured_compact"}:
        command.extend(
            [
                "--replay-dataset",
                str(dataset_path),
                "--benchmark-suite",
                str(benchmark_suite),
                "--out-dir",
                str(out_dir),
                "--provider",
                provider,
            ]
        )
        if model:
            command.extend(["--model", model])
        command.extend(["--max-evidence-records", str(max_evidence_records)])
        return command

    agent_type = {
        "generic_react": "react",
        "bounded_react": "bounded_react",
        "diagnostic": "diagnostic",
    }[variant]
    command.extend(
        [
            "--agent-type",
            agent_type,
            "--backend",
            "replay",
            "--replay-dataset",
            str(dataset_path),
            "--benchmark-suite",
            str(benchmark_suite),
            "--problem-id",
            infer_problem_id(dataset_path),
            "--out-file",
            str(out_dir / "agent_report.json"),
            "--provider",
            provider,
            "--max-steps",
            str(max_steps),
            "--evidence-view",
            "distilled",
        ]
    )
    if model:
        command.extend(["--model", model])
    return command


def select_episodes(payload: Dict[str, Any], include: str, limit: int) -> List[Path]:
    episodes = [ROOT / str(item) for item in payload.get("episodes", []) or []]
    selected: List[Path] = []
    needle = include.strip().lower()
    for episode in episodes:
        problem_id = infer_problem_id(episode)
        if needle and needle not in str(episode).lower() and needle not in problem_id.lower():
            continue
        selected.append(episode)
    if limit > 0:
        selected = selected[:limit]
    return selected


def summarize_process(proc: subprocess.CompletedProcess[str]) -> Dict[str, Any]:
    def tail(text: str) -> str:
        lines = [line for line in text.splitlines() if line.strip()]
        return "\n".join(lines[-20:])

    return {
        "returncode": proc.returncode,
        "stdout_tail": tail(proc.stdout or ""),
        "stderr_tail": tail(proc.stderr or ""),
    }


def render_markdown(
    *,
    episode_set_name: str,
    variant: str,
    provider: str,
    model: str,
    aggregate: Dict[str, Any],
    episodes_run: List[Dict[str, Any]],
) -> str:
    lines = [
        "# Replay Suite Summary",
        "",
        f"- Episode set: {episode_set_name}",
        f"- Variant: {variant}",
        f"- Provider: {provider}",
        f"- Model: {model or '(provider default)'}",
        f"- Episodes run: {len(episodes_run)}",
        f"- Evaluations aggregated: {aggregate.get('runs', 0)}",
        "",
        "## Episode Runs",
        "",
        "| Problem | Status | Out Dir |",
        "| --- | --- | --- |",
    ]
    for item in episodes_run:
        lines.append(
            f"| {item['problem_id']} | {'ok' if item['returncode'] == 0 else 'error'} | {item['out_dir']} |"
        )
    lines.append("")

    groups = dict(aggregate.get("groups", {}) or {})
    if groups.get("diagnosis_category"):
        lines.extend(
            [
                "## Diagnosis Category",
                "",
                "| Category | Runs | Exact | Family | Action |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in groups["diagnosis_category"]:
            lines.append(
                "| {key} | {runs} | {diagnosis_accuracy:.3f} | {diagnosis_family_accuracy:.3f} | {action_accuracy:.3f} |".format(
                    **row
                )
            )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = build_parser().parse_args()
    episode_set_path = Path(args.episode_set).resolve()
    benchmark_suite = Path(args.benchmark_suite).resolve()
    episode_set = load_episode_set(episode_set_path)
    selected_episodes = select_episodes(episode_set, args.include, args.limit)
    if not selected_episodes:
        raise RuntimeError("no episodes selected")

    out_root = (
        Path(args.out_root).resolve()
        if args.out_root
        else ROOT / "results" / "replay_runs" / f"{args.variant}_{utc_compact()}"
    )
    out_root.mkdir(parents=True, exist_ok=True)

    runs: List[Dict[str, Any]] = []
    for dataset_path in selected_episodes:
        problem_id = infer_problem_id(dataset_path)
        out_dir = out_root / f"{args.variant}__{dataset_path.stem}"
        out_dir.mkdir(parents=True, exist_ok=True)
        command = build_episode_command(
            variant=args.variant,
            dataset_path=dataset_path,
            out_dir=out_dir,
            benchmark_suite=benchmark_suite,
            provider=args.provider,
            model=args.model,
            max_steps=args.max_steps,
            max_evidence_records=args.max_evidence_records,
        )
        proc = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        run_summary = {
            "problem_id": problem_id,
            "dataset": str(dataset_path),
            "out_dir": str(out_dir),
            "command": command,
            **summarize_process(proc),
        }
        runs.append(run_summary)

    taxonomy = load_episode_taxonomy(ROOT / "configs" / "episode_taxonomy.yaml")
    evaluations = load_run_evaluations(out_root)
    aggregate = aggregate_evaluations(evaluations, taxonomy=taxonomy)

    (out_root / "run_summary.json").write_text(json.dumps({"runs": runs}, indent=2))
    (out_root / "aggregate_results.json").write_text(json.dumps(aggregate, indent=2))
    (out_root / "aggregate_results.md").write_text(
        render_markdown(
            episode_set_name=str(episode_set.get("name", episode_set_path.stem)),
            variant=args.variant,
            provider=args.provider,
            model=args.model,
            aggregate=aggregate,
            episodes_run=runs,
        )
    )

    print(
        json.dumps(
            {
                "episode_set": str(episode_set_path),
                "variant": args.variant,
                "provider": args.provider,
                "model": args.model,
                "out_root": str(out_root),
                "episodes": len(selected_episodes),
                "evaluations": len(evaluations),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
