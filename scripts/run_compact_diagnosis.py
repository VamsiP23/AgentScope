#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_graph.evidence_distiller import EVIDENCE_TOOLS, EvidenceDistiller, select_compact_evidence_records
from agent_graph.reasoning.llm import make_json_client
from benchmarking.evaluator import evaluate_agent_run
from benchmarking.problem import load_benchmark_suite
from benchmarking.replay import ReplayDataset


FAULT_CLASSES = [
    "native_service_selector_mismatch",
    "native_service_port_mismatch",
    "native_bad_image_rollout",
    "native_bad_probe_rollout",
    "native_bad_image",
    "native_bad_probe",
    "native_bad_env",
    "native_scale_zero",
    "native_pod_delete",
    "native_dependency_bad_endpoint",
    "native_cpu_limit_throttle",
    "native_memory_limit_oom",
    "native_cpu_pressure_stress_job",
    "native_memory_pressure_stress_job",
    "unknown",
]

ACTION_TYPES = [
    "rollout_undo",
    "rollout_restart",
    "restart_pod",
    "patch_resources",
    "patch_resources_then_scale",
    "patch_service_selector",
    "patch_service_target_port",
    "scale_deployment",
    "delete_stress_job",
    "wait_and_monitor",
    "unknown",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def infer_problem_id(dataset_path: Path, dataset: ReplayDataset) -> str:
    task_id = str(dataset.metadata.get("task_id", "") or dataset_path.stem)
    return re.sub(r"_\d{3}$", "", task_id)


def compact_records(dataset: ReplayDataset, *, max_records: int) -> List[Dict[str, Any]]:
    distiller = EvidenceDistiller()
    rows: List[Dict[str, Any]] = []
    for record in dataset.calls:
        method = str(record.get("method", "")).strip()
        if method not in EVIDENCE_TOOLS:
            continue
        output = dict(record.get("outputs", {}) or {})
        compact = distiller.distill(method, output)
        rows.append(
            {
                "tool": method,
                "inputs": dict(record.get("inputs", {}) or {}),
                "evidence": compact,
            }
        )
    return select_compact_evidence_records(rows, max_records=max_records)


def build_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "root_cause": {"type": "string"},
            "action_taken": {"type": "string"},
            "fault_class": {"type": "string", "enum": FAULT_CLASSES},
            "affected_service": {"type": "string"},
            "action_type": {"type": "string", "enum": ACTION_TYPES},
            "confidence": {"type": "number"},
            "evidence": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "root_cause",
            "action_taken",
            "fault_class",
            "affected_service",
            "action_type",
            "confidence",
            "evidence",
        ],
        "additionalProperties": False,
    }


def build_prompt(dataset: ReplayDataset, evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "task": "Diagnose the incident from compact deterministic evidence. Return one structured submit_solution payload only.",
        "incident_context": dataset.initial_context,
        "important_rules": [
            "This is diagnosis-only replay; do not request or describe live remediation execution.",
            "Use only direct facts visible in the evidence.",
            "Do not assume benchmark ground truth; choose unknown when evidence is insufficient.",
            "Pick exactly one fault_class and one action_type from the provided enums.",
            "Evidence strings should reference tool calls like get_k8s_state(service).",
            "If desired replicas are zero, prefer native_scale_zero with scale_deployment over rollout or pod-restart actions.",
            "If pod deletion/replacement events are visible without image/probe/config failure evidence, prefer native_pod_delete with wait_and_monitor.",
            "If active external stress workload evidence is present, prefer the matching stress-job fault with delete_stress_job; do not patch app resources for latency when app-local CPU/memory/throttling are not saturated.",
            "For dependency/config faults, compare parsed dependency env addresses against Service ports/endpoints when those facts are present.",
            "If a dependency address anomaly is scoped to deployment env/config, prefer rollback/config restoration via rollout_undo over patch_resources.",
            "Only output patch_resources when action_taken changes CPU/memory requests or limits. If action_taken changes an env var, dependency address, or deployed config value, action_type must be rollout_undo.",
            "Do not choose wait_and_monitor for repeated dependency timeout/connection errors tied to a Deployment env address unless evidence shows the dependency recovered.",
        ],
        "fault_class_options": FAULT_CLASSES,
        "action_type_options": ACTION_TYPES,
        "compact_evidence": evidence,
    }


def step_records(evidence: List[Dict[str, Any]], solution: Dict[str, Any]) -> List[Dict[str, Any]]:
    now = time.time()
    steps = []
    for index, item in enumerate(evidence, start=1):
        output = dict(item.get("evidence", {}) or {})
        output.setdefault("call_id", str(uuid4()))
        steps.append(
            {
                "step": index,
                "thought": "Compact evidence supplied to one-shot diagnosis.",
                "tool_called": item.get("tool", ""),
                "call_id": output.get("call_id", ""),
                "inputs": dict(item.get("inputs", {}) or {}),
                "output": output,
                "timestamp": now + index * 0.001,
            }
        )
    submit_output = {
        "call_id": str(uuid4()),
        "timestamp": utc_now(),
        "solution_logged": True,
        "evidence_valid": True,
        "invalid_evidence": [],
        "error": None,
        **solution,
    }
    steps.append(
        {
            "step": len(steps) + 1,
            "thought": "Submit one-shot compact diagnosis.",
            "tool_called": "submit_solution",
            "call_id": submit_output["call_id"],
            "inputs": {},
            "output": submit_output,
            "timestamp": now + (len(steps) + 1) * 0.001,
        }
    )
    return steps


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one-shot diagnosis over compact replay evidence.")
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

    evidence = compact_records(dataset, max_records=args.max_evidence_records)
    prompt = build_prompt(dataset, evidence)
    client = make_json_client(provider=args.provider, model=args.model or None)
    model = client.model

    try:
        solution = client.complete_json(name="compact_diagnosis", schema=build_schema(), prompt=prompt)
    except Exception as exc:
        payload = {
            "timestamp_utc": utc_now(),
            "provider": args.provider,
            "model": model,
            "replay_dataset": str(dataset_path),
            "problem_id": problem_id,
            "error": str(exc),
        }
        error_path.write_text(json.dumps(payload, indent=2))
        print(json.dumps(payload, indent=2))
        return 2

    if solution.get("fault_class") == "unknown":
        solution["fault_class"] = ""
    if solution.get("action_type") == "unknown":
        solution["action_type"] = ""
    solution["confidence"] = float(solution.get("confidence", 0.0) or 0.0)
    solution["evidence"] = [str(item).strip() for item in solution.get("evidence", []) or [] if str(item).strip()]

    steps = step_records(evidence, solution)
    report = {
        "agent_type": "benchmark",
        "timestamp_utc": utc_now(),
        "provider": args.provider,
        "model": model,
        "agent_variant": "compact_one_shot",
        "backend": "replay",
        "diagnosis_only": True,
        "evidence_view": "compact",
        "replay_dataset": str(dataset_path),
        "problem": problem.to_dict(),
        "seeded_detection": {},
        "guardrail_events": [],
        "steps": steps,
        "solution": steps[-1]["output"],
        "verification": {},
        "error": None,
    }
    report_path.write_text(json.dumps(report, indent=2))
    evaluation = evaluate_agent_run(problem, report).to_dict()
    evaluation_path.write_text(json.dumps(evaluation, indent=2))
    print(json.dumps({"agent_report": str(report_path), "evaluation": str(evaluation_path), "evaluation_summary": evaluation}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
