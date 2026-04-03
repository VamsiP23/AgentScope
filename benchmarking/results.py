from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def load_run_evaluations(run_root: Path) -> List[Dict[str, Any]]:
    evaluations: List[Dict[str, Any]] = []
    for evaluation_path in sorted(run_root.glob("*/evaluation.json")):
        try:
            payload = json.loads(evaluation_path.read_text())
        except Exception:
            continue
        payload["_run_dir"] = str(evaluation_path.parent)
        evaluations.append(payload)
    return evaluations


def aggregate_evaluations(evaluations: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_problem: Dict[str, Dict[str, Any]] = {}
    for item in evaluations:
        problem_id = str(item.get("problem_id", "") or "unmapped")
        agent_variant = str(item.get("agent_variant", "") or "unknown")
        key = f"{problem_id}::{agent_variant}"
        bucket = by_problem.setdefault(
            key,
            {
                "problem_id": problem_id,
                "agent_variant": agent_variant,
                "agent_type": str(item.get("agent_type", "") or "unknown"),
                "models": set(),
                "runs": 0,
                "incident_detected_rate": 0.0,
                "diagnosis_accuracy": 0.0,
                "action_accuracy": 0.0,
                "avg_tool_calls_to_solution": 0.0,
                "avg_time_to_diagnosis_seconds": 0.0,
                "avg_repeated_call_count": 0.0,
                "avg_evidence_coverage": 0.0,
            },
        )
        bucket["models"].add(str(item.get("model", "") or ""))
        bucket["runs"] += 1
        bucket["incident_detected_rate"] += 1.0 if item.get("incident_detected") else 0.0
        bucket["diagnosis_accuracy"] += 1.0 if item.get("diagnosis_correct") else 0.0
        bucket["action_accuracy"] += 1.0 if item.get("action_correct") else 0.0
        bucket["avg_tool_calls_to_solution"] += float(item.get("tool_calls_to_solution", 0) or 0.0)
        bucket["avg_time_to_diagnosis_seconds"] += float(item.get("time_to_diagnosis_seconds") or 0.0)
        bucket["avg_repeated_call_count"] += float(item.get("repeated_call_count", 0) or 0.0)
        bucket["avg_evidence_coverage"] += float(item.get("evidence_coverage", 0.0) or 0.0)

    for bucket in by_problem.values():
        runs = max(1, int(bucket["runs"]))
        bucket["models"] = sorted(model for model in bucket["models"] if model)
        for key in (
            "incident_detected_rate",
            "diagnosis_accuracy",
            "action_accuracy",
            "avg_tool_calls_to_solution",
            "avg_time_to_diagnosis_seconds",
            "avg_repeated_call_count",
            "avg_evidence_coverage",
        ):
            bucket[key] = round(float(bucket[key]) / runs, 3)

    overall = {
        "runs": len(evaluations),
        "problems": sorted(by_problem.values(), key=lambda item: (item["problem_id"], item["agent_variant"])),
    }
    return overall
