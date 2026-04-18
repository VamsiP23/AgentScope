from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml


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


def load_episode_taxonomy(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text())
    return payload if isinstance(payload, dict) else {}


def taxonomy_for_evaluation(evaluation: Dict[str, Any], taxonomy: Dict[str, Any]) -> Dict[str, Any]:
    family = str(evaluation.get("expected_fault_class", "") or evaluation.get("problem_id", "")).strip()
    family_labels = dict(taxonomy.get("families", {}) or {})
    item = dict(family_labels.get(family, {}) or {})
    if not item:
        item = _infer_taxonomy(family)
    category_id = str(item.get("diagnosis_category", "uncategorized") or "uncategorized")
    categories = dict(taxonomy.get("categories", {}) or {})
    category = dict(categories.get(category_id, {}) or {})
    return {
        "fault_family": family,
        "diagnosis_category": category_id,
        "diagnosis_category_label": str(category.get("label", category_id)),
        "difficulty": str(item.get("difficulty", "unknown") or "unknown"),
        "primary_tools": list(item.get("primary_tools", []) or []),
        "secondary_tools": list(item.get("secondary_tools", []) or []),
        "trace_required": bool(item.get("trace_required", False)),
    }


def aggregate_evaluations(
    evaluations: List[Dict[str, Any]],
    taxonomy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    taxonomy = taxonomy or {}
    by_problem: Dict[str, Dict[str, Any]] = {}
    for item in evaluations:
        item_taxonomy = taxonomy_for_evaluation(item, taxonomy) if taxonomy else {}
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
                "diagnosis_family_accuracy": 0.0,
                "action_accuracy": 0.0,
                "avg_tool_calls_to_solution": 0.0,
                "avg_time_to_diagnosis_seconds": 0.0,
                "avg_repeated_call_count": 0.0,
                "avg_evidence_coverage": 0.0,
                "taxonomy": item_taxonomy,
            },
        )
        bucket["models"].add(str(item.get("model", "") or ""))
        bucket["runs"] += 1
        bucket["incident_detected_rate"] += 1.0 if item.get("incident_detected") else 0.0
        bucket["diagnosis_accuracy"] += 1.0 if item.get("diagnosis_correct") else 0.0
        bucket["diagnosis_family_accuracy"] += 1.0 if item.get("diagnosis_family_correct", item.get("diagnosis_correct")) else 0.0
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
            "diagnosis_family_accuracy",
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
    if taxonomy:
        overall["groups"] = {
            "diagnosis_category": _aggregate_groups(
                evaluations,
                taxonomy,
                lambda item, labels: str(labels.get("diagnosis_category", "uncategorized")),
            ),
            "difficulty": _aggregate_groups(
                evaluations,
                taxonomy,
                lambda item, labels: str(labels.get("difficulty", "unknown")),
            ),
            "trace_required": _aggregate_groups(
                evaluations,
                taxonomy,
                lambda item, labels: "trace_required" if labels.get("trace_required") else "trace_not_required",
            ),
            "fault_family": _aggregate_groups(
                evaluations,
                taxonomy,
                lambda item, labels: str(labels.get("fault_family", item.get("problem_id", "unmapped"))),
            ),
        }
    return overall


def _aggregate_groups(
    evaluations: Iterable[Dict[str, Any]],
    taxonomy: Dict[str, Any],
    key_fn: Any,
) -> List[Dict[str, Any]]:
    buckets: Dict[str, Dict[str, Any]] = {}
    for item in evaluations:
        labels = taxonomy_for_evaluation(item, taxonomy)
        key = key_fn(item, labels)
        bucket = buckets.setdefault(
            key,
            {
                "key": key,
                "runs": 0,
                "diagnosis_accuracy": 0.0,
                "diagnosis_family_accuracy": 0.0,
                "action_accuracy": 0.0,
                "valid_submission_rate": 0.0,
                "avg_tool_calls_to_solution": 0.0,
                "avg_time_to_diagnosis_seconds": 0.0,
                "avg_repeated_call_count": 0.0,
                "avg_evidence_coverage": 0.0,
            },
        )
        bucket["runs"] += 1
        bucket["diagnosis_accuracy"] += 1.0 if item.get("diagnosis_correct") else 0.0
        bucket["diagnosis_family_accuracy"] += 1.0 if item.get("diagnosis_family_correct", item.get("diagnosis_correct")) else 0.0
        bucket["action_accuracy"] += 1.0 if item.get("action_correct") else 0.0
        bucket["valid_submission_rate"] += 0.0 if item.get("invalid_submit_count") else 1.0
        bucket["avg_tool_calls_to_solution"] += float(item.get("tool_calls_to_solution", 0) or 0.0)
        bucket["avg_time_to_diagnosis_seconds"] += float(item.get("time_to_diagnosis_seconds") or 0.0)
        bucket["avg_repeated_call_count"] += float(item.get("repeated_call_count", 0) or 0.0)
        bucket["avg_evidence_coverage"] += float(item.get("evidence_coverage", 0.0) or 0.0)
    for bucket in buckets.values():
        runs = max(1, int(bucket["runs"]))
        for metric in (
            "diagnosis_accuracy",
            "diagnosis_family_accuracy",
            "action_accuracy",
            "valid_submission_rate",
            "avg_tool_calls_to_solution",
            "avg_time_to_diagnosis_seconds",
            "avg_repeated_call_count",
            "avg_evidence_coverage",
        ):
            bucket[metric] = round(float(bucket[metric]) / runs, 3)
    return sorted(buckets.values(), key=lambda item: item["key"])


def _infer_taxonomy(family: str) -> Dict[str, Any]:
    if family in {"native_bad_env", "native_dependency_bad_endpoint"}:
        return {
            "diagnosis_category": "dependency_path_trace_centered",
            "difficulty": "causal_path",
            "trace_required": True,
        }
    if any(token in family for token in ("service_port", "service_selector")):
        return {
            "diagnosis_category": "service_wiring_configuration",
            "difficulty": "contrast_required",
            "trace_required": False,
        }
    if any(token in family for token in ("cpu", "memory", "oom", "pressure", "throttle")):
        return {
            "diagnosis_category": "resource_performance",
            "difficulty": "contrast_required",
            "trace_required": False,
        }
    if any(token in family for token in ("rollout", "image", "probe", "scale", "pod_delete")):
        return {
            "diagnosis_category": "availability_rollout",
            "difficulty": "direct_signal",
            "trace_required": False,
        }
    return {"diagnosis_category": "uncategorized", "difficulty": "unknown", "trace_required": False}
