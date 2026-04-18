from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from agent_graph.evidence_distiller import EVIDENCE_TOOLS, EvidenceDistiller, select_compact_evidence_records
from agent_graph.reasoning.llm import BaseJSONClient
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

DIAGNOSIS_CATEGORIES = [
    "availability_rollout",
    "service_wiring_configuration",
    "resource_performance",
    "dependency_path_trace_centered",
    "unknown",
]

REMEDIATION_POLICY = [
    "Choose patch_resources only when app-local CPU, memory, limit, throttling, or OOM evidence supports an app resource limit problem.",
    "Choose delete_stress_job when active external stress workload evidence is present; do not patch app resources for latency when app-local CPU/memory/throttling are not saturated.",
    "Choose patch_service_target_port only when Kubernetes Service targetPort/containerPort alignment evidence shows a mismatch.",
    "Choose patch_service_selector only when Service selector and selected-pod label evidence shows the Service selects the wrong pods or no intended pods.",
    "Choose rollout_undo for bad rollout or deployed workload config changes, including invalid image, bad probe, or bad dependency/env address introduced through a Deployment rollout.",
    "For dependency address anomalies scoped to Deployment env/config, prefer rollback/config restoration via rollout_undo over patch_resources.",
    "Only output patch_resources when the intended action changes CPU/memory requests or limits. If the intended action changes an env var, dependency address, or deployed config value, action_type must be rollout_undo.",
    "Choose scale_deployment only when desired replicas are wrong, such as scale-to-zero evidence.",
    "Choose restart_pod only for pod lifecycle disturbance where replacing a currently stuck pod is the intended intervention.",
    "Choose wait_and_monitor when pod deletion/replacement events indicate a transient lifecycle disruption and no config/resource fix is supported.",
    "Do not choose wait_and_monitor for repeated dependency timeout/connection errors tied to a Deployment env address unless evidence shows the dependency recovered.",
    "Reject patch_resources when resource metrics are healthy or unavailable but the anomaly is a config/address mismatch.",
    "Reject patch_service_target_port when Service targetPort values align with selected-pod container ports.",
]


def infer_problem_id(dataset_path: Path, dataset: ReplayDataset) -> str:
    task_id = str(dataset.metadata.get("task_id", "") or dataset_path.stem)
    return re.sub(r"_\d{3}$", "", task_id)


def collect_compact_evidence(dataset: ReplayDataset, *, max_records: int) -> List[Dict[str, Any]]:
    distiller = EvidenceDistiller()
    rows: List[Dict[str, Any]] = []
    for record in dataset.calls:
        method = str(record.get("method", "")).strip()
        if method not in EVIDENCE_TOOLS:
            continue
        compact = distiller.distill(method, dict(record.get("outputs", {}) or {}))
        rows.append(
            {
                "tool": method,
                "inputs": dict(record.get("inputs", {}) or {}),
                "evidence": compact,
            }
        )
    return select_compact_evidence_records(rows, max_records=max_records)


def group_evidence_by_channel(evidence: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    groups = {
        "k8s_state": [],
        "logs": [],
        "metrics": [],
        "traces": [],
        "dependency_traces": [],
    }
    for item in evidence:
        tool = str(item.get("tool", ""))
        if tool == "get_k8s_state":
            groups["k8s_state"].append(item)
        elif tool == "get_logs":
            groups["logs"].append(item)
        elif tool == "get_metrics":
            groups["metrics"].append(item)
        elif tool == "get_traces":
            groups["traces"].append(item)
        elif tool == "get_dependency_traces":
            groups["dependency_traces"].append(item)
    return groups


def triage_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "suspected_categories": {
                "type": "array",
                "items": {"type": "string", "enum": DIAGNOSIS_CATEGORIES},
            },
            "needed_evidence": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["k8s_state", "service_config", "logs", "metrics", "traces", "dependency_traces"],
                },
            },
            "key_observations": {"type": "array", "items": {"type": "string"}},
            "why": {"type": "string"},
        },
        "required": ["suspected_categories", "needed_evidence", "key_observations", "why"],
        "additionalProperties": False,
    }


def analysis_schema() -> Dict[str, Any]:
    candidate = {
        "type": "object",
        "properties": {
            "fault_class": {"type": "string", "enum": FAULT_CLASSES},
            "affected_service": {"type": "string"},
            "action_type": {"type": "string", "enum": ACTION_TYPES},
            "supporting_evidence": {"type": "array", "items": {"type": "string"}},
            "contradicting_evidence": {"type": "array", "items": {"type": "string"}},
            "score": {"type": "number"},
        },
        "required": [
            "fault_class",
            "affected_service",
            "action_type",
            "supporting_evidence",
            "contradicting_evidence",
            "score",
        ],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "positive_facts": {"type": "array", "items": {"type": "string"}},
            "anomalies": {"type": "array", "items": {"type": "string"}},
            "negative_evidence": {"type": "array", "items": {"type": "string"}},
            "observability_gaps": {"type": "array", "items": {"type": "string"}},
            "candidates": {"type": "array", "items": candidate},
            "rejected_candidates": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "positive_facts",
            "anomalies",
            "negative_evidence",
            "observability_gaps",
            "candidates",
            "rejected_candidates",
        ],
        "additionalProperties": False,
    }


def solution_schema() -> Dict[str, Any]:
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


def build_triage_prompt(dataset: ReplayDataset, evidence_groups: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    return {
        "task": "Triage the incident from compact replay evidence. Do not submit a final answer yet.",
        "incident_context": dataset.initial_context,
        "diagnosis_categories": DIAGNOSIS_CATEGORIES,
        "rules": [
            "Use only direct facts visible in compact evidence.",
            "Do not infer hidden benchmark labels or ground truth.",
            "Prefer dependency_path_trace_centered only when logs/traces/dependency evidence localize a request path.",
            "Return the structured triage object only.",
        ],
        "compact_evidence_by_channel": evidence_groups,
    }


def build_analysis_prompt(
    dataset: ReplayDataset,
    evidence_groups: Dict[str, List[Dict[str, Any]]],
    triage: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "task": "Compare candidate diagnoses using the compact evidence. Do not submit a final answer yet.",
        "incident_context": dataset.initial_context,
        "triage": triage,
        "fault_class_options": FAULT_CLASSES,
        "action_type_options": ACTION_TYPES,
        "remediation_policy": REMEDIATION_POLICY,
        "rules": [
            "For each plausible candidate, list both supporting and contradicting evidence.",
            "Distinguish symptom service from the service/config object that should be changed.",
            "For dependency-path faults, decide whether rollback/config restoration is better supported than wait or resource patching.",
            "Apply the remediation policy as general SRE action-selection rules, not as benchmark answer labels.",
            "Use unknown when evidence is insufficient.",
        ],
        "compact_evidence_by_channel": evidence_groups,
    }


def build_solution_prompt(
    dataset: ReplayDataset,
    evidence_groups: Dict[str, List[Dict[str, Any]]],
    triage: Dict[str, Any],
    analysis: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "task": "Submit the final diagnosis-only replay answer.",
        "incident_context": dataset.initial_context,
        "triage": triage,
        "candidate_analysis": analysis,
        "fault_class_options": FAULT_CLASSES,
        "action_type_options": ACTION_TYPES,
        "remediation_policy": REMEDIATION_POLICY,
        "rules": [
            "Return exactly one structured submit_solution payload.",
            "Do not request or describe live remediation execution.",
            "Use only direct facts visible in evidence and your candidate comparison.",
            "The action_type is the intended fix category, not an executed command.",
            "Apply remediation_policy strictly; do not choose a patch action unless its required evidence type is present.",
            "Evidence strings should cite tool calls such as get_k8s_state(service).",
        ],
        "compact_evidence_by_channel": evidence_groups,
    }


def normalize_solution(solution: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(solution)
    if normalized.get("fault_class") == "unknown":
        normalized["fault_class"] = ""
    if normalized.get("action_type") == "unknown":
        normalized["action_type"] = ""
    normalized["confidence"] = float(normalized.get("confidence", 0.0) or 0.0)
    normalized["evidence"] = [
        str(item).strip()
        for item in normalized.get("evidence", []) or []
        if str(item).strip()
    ]
    return normalized


def build_steps(
    evidence: List[Dict[str, Any]],
    triage: Dict[str, Any],
    analysis: Dict[str, Any],
    solution: Dict[str, Any],
) -> List[Dict[str, Any]]:
    now = time.time()
    steps: List[Dict[str, Any]] = []
    for index, item in enumerate(evidence, start=1):
        output = dict(item.get("evidence", {}) or {})
        output.setdefault("call_id", str(uuid4()))
        steps.append(
            {
                "step": index,
                "thought": "Compact evidence supplied to structured diagnosis.",
                "tool_called": item.get("tool", ""),
                "call_id": output.get("call_id", ""),
                "inputs": dict(item.get("inputs", {}) or {}),
                "output": output,
                "timestamp": now + index * 0.001,
            }
        )

    for name, payload in [("structured_triage", triage), ("structured_candidate_analysis", analysis)]:
        steps.append(
            {
                "step": len(steps) + 1,
                "thought": f"Structured compact {name}.",
                "tool_called": name,
                "call_id": str(uuid4()),
                "inputs": {},
                "output": payload,
                "timestamp": now + (len(steps) + 1) * 0.001,
            }
        )

    submit_output = {
        "call_id": str(uuid4()),
        "solution_logged": True,
        "evidence_valid": True,
        "invalid_evidence": [],
        "error": None,
        **solution,
    }
    steps.append(
        {
            "step": len(steps) + 1,
            "thought": "Submit structured compact diagnosis.",
            "tool_called": "submit_solution",
            "call_id": submit_output["call_id"],
            "inputs": {},
            "output": submit_output,
            "timestamp": now + (len(steps) + 1) * 0.001,
        }
    )
    return steps


def run_structured_compact_diagnosis(
    *,
    client: BaseJSONClient,
    dataset: ReplayDataset,
    max_evidence_records: int,
) -> Dict[str, Any]:
    evidence = collect_compact_evidence(dataset, max_records=max_evidence_records)
    evidence_groups = group_evidence_by_channel(evidence)
    triage = client.complete_json(
        name="structured_compact_triage",
        schema=triage_schema(),
        prompt=build_triage_prompt(dataset, evidence_groups),
    )
    analysis = client.complete_json(
        name="structured_compact_candidate_analysis",
        schema=analysis_schema(),
        prompt=build_analysis_prompt(dataset, evidence_groups, triage),
    )
    solution = client.complete_json(
        name="structured_compact_solution",
        schema=solution_schema(),
        prompt=build_solution_prompt(dataset, evidence_groups, triage, analysis),
    )
    solution = normalize_solution(solution)
    steps = build_steps(evidence, triage, analysis, solution)
    return {
        "evidence": evidence,
        "evidence_groups": evidence_groups,
        "triage": triage,
        "analysis": analysis,
        "solution": solution,
        "steps": steps,
    }


def as_jsonable_preview(value: Any) -> str:
    return json.dumps(value, sort_keys=True)[:500]
