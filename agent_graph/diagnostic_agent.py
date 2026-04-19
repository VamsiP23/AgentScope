from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

from agent_graph.react_support import default_model, normalize_provider, normalize_service_name
from agent_graph.reasoning.llm import ResponsesJSONClient
from agent_graph.structured_compact_agent import (
    ACTION_TYPES,
    DIAGNOSIS_CATEGORIES,
    FAULT_CLASSES,
    REMEDIATION_POLICY,
)


EVIDENCE_TOOLS = {
    "get_k8s_state",
    "get_metrics",
    "get_logs",
    "get_traces",
    "get_dependency_traces",
    "get_cluster_resource_context",
}


class DiagnosticEvidenceLedger:
    """Small deterministic state object that records what the agent has inspected."""

    def __init__(self) -> None:
        self.records: List[Dict[str, Any]] = []
        self.tools_seen: set[str] = set()
        self.tool_services_seen: set[Tuple[str, str]] = set()
        self.facts: List[str] = []
        self.anomalies: List[str] = []
        self.negative_evidence: List[str] = []
        self.observability_gaps: List[str] = []
        self.raw_refs: List[Dict[str, Any]] = []
        self.flags: Dict[str, bool] = {
            "service_wiring_checked": False,
            "service_wiring_anomaly": False,
            "metrics_checked": False,
            "resource_anomaly": False,
            "oom_evidence": False,
            "external_pressure_checked": False,
            "external_pressure_anomaly": False,
            "logs_checked": False,
            "dependency_log_signal": False,
            "traces_checked": False,
            "dependency_trace_signal": False,
            "rollout_or_probe_signal": False,
            "image_pull_signal": False,
            "pod_lifecycle_signal": False,
        }

    def add(self, *, tool: str, service: str, output: Dict[str, Any]) -> None:
        self.records.append({"tool": tool, "service": service, "output": output})
        self.tools_seen.add(tool)
        self.tool_services_seen.add((tool, service))
        if tool == "get_k8s_state":
            self.flags["service_wiring_checked"] = True
        elif tool == "get_metrics":
            self.flags["metrics_checked"] = True
        elif tool == "get_logs":
            self.flags["logs_checked"] = True
        elif tool in {"get_traces", "get_dependency_traces"}:
            self.flags["traces_checked"] = True
        elif tool == "get_cluster_resource_context":
            self.flags["external_pressure_checked"] = True

        self._extend_unique(self.facts, self._stringify_items(output.get("key_facts", [])), limit=36)
        self._extend_unique(self.anomalies, self._stringify_items(output.get("anomalies", [])), limit=24)
        self._extend_unique(self.negative_evidence, self._stringify_items(output.get("negative_evidence", [])), limit=24)
        self._extend_unique(self.observability_gaps, self._stringify_items(output.get("observability_gaps", [])), limit=16)
        for ref in output.get("raw_refs", []) or []:
            if isinstance(ref, dict) and ref not in self.raw_refs:
                self.raw_refs.append(ref)

        blob = self._blob(output)
        anomaly_blob = self._blob(output.get("anomalies", []))
        if any(token in blob for token in ["port_inconsistency", "selector", "targetport", "endpoint"]):
            self.flags["service_wiring_anomaly"] = True
        if tool == "get_metrics" and any(
            token in anomaly_blob for token in ["cpu", "memory", "throttl", "oom", "resource", "saturation", "pressure"]
        ):
            self.flags["resource_anomaly"] = True
        if any(token in blob for token in ["oomkilled", "exit 137", "out of memory", "memory_limit_oom"]):
            self.flags["oom_evidence"] = True
        if "external_resource_pressure" in blob or "non-application workload" in blob:
            self.flags["external_pressure_anomaly"] = True
        if any(token in blob for token in ["connection", "timeout", "dependency", "downstream", "upstream"]):
            if tool == "get_logs":
                self.flags["dependency_log_signal"] = True
            if tool in {"get_traces", "get_dependency_traces"}:
                self.flags["dependency_trace_signal"] = True
        if any(token in blob for token in ["probe", "readiness", "liveness"]):
            self.flags["rollout_or_probe_signal"] = True
        if any(token in blob for token in ["imagepull", "errimagepull", "invalid image", "pull image"]):
            self.flags["image_pull_signal"] = True
        if any(token in blob for token in ["successfuldelete", "successfulcreate", "killing", "pod_lifecycle", "replacement"]):
            self.flags["pod_lifecycle_signal"] = True

    def seen(self, tool: str, service: str = "") -> bool:
        if service:
            return (tool, service) in self.tool_services_seen
        return tool in self.tools_seen

    def to_prompt(self) -> Dict[str, Any]:
        return {
            "tools_seen": sorted(self.tools_seen),
            "flags": dict(self.flags),
            "facts": list(self.facts),
            "anomalies": list(self.anomalies),
            "negative_evidence": list(self.negative_evidence),
            "observability_gaps": list(self.observability_gaps),
            "raw_refs": self.raw_refs[:8],
        }

    def compact_records(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for record in self.records:
            output = dict(record.get("output", {}) or {})
            rows.append(
                {
                    "tool": record.get("tool", ""),
                    "service": record.get("service", ""),
                    "status": output.get("status", ""),
                    "summary": output.get("summary", ""),
                    "key_facts": output.get("key_facts", [])[:10],
                    "anomalies": output.get("anomalies", [])[:8],
                    "negative_evidence": output.get("negative_evidence", [])[:6],
                    "observability_gaps": output.get("observability_gaps", [])[:4],
                    "raw_refs": output.get("raw_refs", [])[:4],
                }
            )
        return rows

    def evidence_strings(self) -> List[str]:
        evidence: List[str] = []
        for record in self.records:
            tool = str(record.get("tool", ""))
            service = str(record.get("service", ""))
            if tool and service and tool != "get_dependency_traces":
                evidence.append(f"{tool}({service})")
            elif tool == "get_dependency_traces":
                evidence.append(f"{tool}({service})")
        return evidence

    def missing_for_fault(self, fault_class: str) -> List[str]:
        fault = fault_class.strip()
        flags = self.flags
        missing: List[str] = []
        if fault in {"native_dependency_config_regression", "native_dependency_bad_endpoint", "native_bad_env"} and not flags["traces_checked"]:
            missing.append("dependency traces have not been inspected")
        if fault in {
            "native_cpu_limit_throttle",
            "native_memory_limit_oom",
            "native_cpu_pressure_stress_job",
            "native_memory_pressure_stress_job",
        } and not flags["metrics_checked"]:
            missing.append("metrics have not been inspected")
        if fault in {"native_cpu_pressure_stress_job", "native_memory_pressure_stress_job"} and not flags[
            "external_pressure_checked"
        ]:
            missing.append("cluster resource context has not been inspected")
        if fault == "native_memory_limit_oom" and not flags["oom_evidence"]:
            missing.append("OOM-specific evidence is absent")
        if fault in {"native_service_port_mismatch", "native_service_selector_mismatch"} and not flags[
            "service_wiring_checked"
        ]:
            missing.append("service wiring has not been inspected")
        return missing

    @staticmethod
    def _blob(value: Any) -> str:
        return str(value).lower()

    @staticmethod
    def _stringify_items(items: Any) -> List[str]:
        return [str(item) for item in list(items or []) if str(item).strip()]

    @staticmethod
    def _extend_unique(target: List[str], values: List[str], *, limit: int) -> None:
        for value in values:
            if value not in target:
                target.append(value)
            if len(target) >= limit:
                return


class DiagnosticAgent:
    """Autonomous diagnosis controller with a structured evidence ledger."""

    def __init__(
        self,
        aci: Any,
        provider: str | None = None,
        model: str | None = None,
        max_steps: int = 12,
        diagnosis_only: bool = False,
        step_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.aci = aci
        self.provider = normalize_provider(provider or os.environ.get("LLM_PROVIDER", "openai"))
        self.model = model or default_model(self.provider)
        self.max_steps = max_steps
        self.diagnosis_only = diagnosis_only
        self.step_callback = step_callback
        self.client = ResponsesJSONClient(model=self.model, provider=self.provider)
        if not self.client.available():
            raise RuntimeError(f"LLM provider '{self.provider}' is not configured")
        self.ledger = DiagnosticEvidenceLedger()
        self.steps: List[Dict[str, Any]] = []
        self.llm_events: List[Dict[str, Any]] = []
        self._initial_context: Dict[str, Any] = {}

    def run(self, problem_description: str, initial_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.ledger = DiagnosticEvidenceLedger()
        self.steps = []
        self.llm_events = []
        self._initial_context = initial_context or {}

        focus_service = self._default_service()
        for tool in ["get_k8s_state", "get_metrics", "get_logs"]:
            self._execute_evidence_tool(tool, focus_service)

        hypotheses = self._call_hypothesis(problem_description)
        for tool, service in self._plan_follow_up_tools(hypotheses, limit=3):
            self._execute_evidence_tool(tool, service)

        verification = self._call_verifier(problem_description, hypotheses)
        if not bool(verification.get("ready_to_submit", False)) and not self._verification_has_complete_supported_solution(
            verification
        ):
            for tool, service in self._plan_repair_tools(verification, limit=2):
                self._execute_evidence_tool(tool, service)
            verification = self._call_verifier(problem_description, hypotheses, repair=True)

        solution = self._solution_from_verification(verification)
        missing = self.ledger.missing_for_fault(solution.get("fault_class", ""))
        if missing:
            verification = self._call_verifier(
                problem_description,
                hypotheses,
                repair=True,
                forced_feedback={"missing_required_evidence": missing},
            )
            solution = self._solution_from_verification(verification)

        submit_step = self._submit(solution)
        return {
            "agent_type": "diagnostic",
            "provider": self.provider,
            "model": self.model,
            "agent_variant": "diagnostic_controller",
            "diagnostic_events": list(self.llm_events),
            "evidence_ledger": self.ledger.to_prompt(),
            "steps": list(self.steps),
            "solution": submit_step["output"],
        }

    def _execute_evidence_tool(self, tool: str, service: str) -> Dict[str, Any]:
        service = normalize_service_name(service or self._default_service())
        if tool != "get_cluster_resource_context" and self.ledger.seen(tool, service):
            return {}
        if tool == "get_cluster_resource_context" and self.ledger.seen(tool, service):
            return {}

        if tool == "get_k8s_state":
            output = self.aci.get_k8s_state(service)
        elif tool == "get_metrics":
            output = self.aci.get_metrics(service, lookback_minutes=5)
        elif tool == "get_logs":
            output = self.aci.get_logs(service, tail_lines=100)
        elif tool == "get_traces":
            output = self.aci.get_traces(service, lookback_minutes=5)
        elif tool == "get_dependency_traces":
            output = self.aci.get_dependency_traces(service, entry_service="frontend", lookback_minutes=5)
        elif tool == "get_cluster_resource_context":
            getter = getattr(self.aci, "get_cluster_resource_context", None)
            if not callable(getter):
                output = {
                    "call_id": str(uuid4()),
                    "timestamp": time.time(),
                    "error": "get_cluster_resource_context is not available for this backend",
                }
            else:
                output = getter(service)
        else:
            raise RuntimeError(f"unsupported diagnostic evidence tool: {tool}")

        self.ledger.add(tool=tool, service=service, output=output)
        step = {
            "step": len(self.steps) + 1,
            "thought": f"Diagnostic controller collected {tool} for {service}.",
            "tool_called": tool,
            "call_id": output.get("call_id", ""),
            "inputs": self._tool_inputs(tool, service),
            "output": output,
            "timestamp": time.time(),
        }
        self._record_step(step)
        return output

    def _call_hypothesis(self, problem_description: str) -> Dict[str, Any]:
        prompt = {
            "task": "Rank incident hypotheses from the evidence ledger. Do not submit a final answer.",
            "problem_description": problem_description,
            "incident_context": self._initial_context,
            "diagnosis_categories": DIAGNOSIS_CATEGORIES,
            "fault_class_options": FAULT_CLASSES,
            "action_type_options": ACTION_TYPES,
            "remediation_policy": REMEDIATION_POLICY,
            "evidence_ledger": self.ledger.to_prompt(),
            "compact_evidence_records": self.ledger.compact_records(),
            "rules": [
                "Use only direct facts visible in evidence.",
                "Rank competing hypotheses and identify what evidence would distinguish the top two.",
                "Do not choose a narrower class unless the ledger has evidence for that distinction.",
                "Do not submit a solution in this stage.",
            ],
        }
        result = self.client.complete_json(
            name="diagnostic_hypotheses",
            schema=self._hypothesis_schema(),
            prompt=prompt,
        )
        self._record_llm_event("diagnostic_hypotheses", result)
        return result

    def _call_verifier(
        self,
        problem_description: str,
        hypotheses: Dict[str, Any],
        *,
        repair: bool = False,
        forced_feedback: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        prompt = {
            "task": "Verify whether the agent can submit a diagnosis/action now.",
            "mode": "repair_verification" if repair else "final_verification",
            "problem_description": problem_description,
            "incident_context": self._initial_context,
            "fault_class_options": FAULT_CLASSES,
            "action_type_options": ACTION_TYPES,
            "remediation_policy": REMEDIATION_POLICY,
            "hypotheses": hypotheses,
            "evidence_ledger": self.ledger.to_prompt(),
            "compact_evidence_records": self.ledger.compact_records(),
            "required_evidence_checks": [
                "Dependency diagnoses require trace inspection when traces are available.",
                "Resource diagnoses require metrics.",
                "External stress diagnoses require cluster resource context when available.",
                "Memory OOM requires OOM-specific events, restarts, or logs, not just high utilization.",
                "Bad probe/rollout requires current rollout/probe/image evidence, not merely recovered lifecycle noise.",
            ],
            "forced_feedback": forced_feedback or {},
            "rules": [
                "If required evidence is missing, set ready_to_submit=false and request the smallest next tool.",
                "If ready, return exactly one diagnosis/action payload.",
                "The action_type is the intended remediation category; do not claim live remediation execution.",
                "Cite evidence using tool(service) strings where possible.",
            ],
        }
        result = self.client.complete_json(
            name="diagnostic_verifier",
            schema=self._verifier_schema(),
            prompt=prompt,
        )
        self._record_llm_event("diagnostic_verifier", result)
        return result

    def _submit(self, solution: Dict[str, Any]) -> Dict[str, Any]:
        output = self.aci.submit_solution(
            root_cause=str(solution.get("root_cause", "")).strip(),
            action_taken=str(solution.get("action_taken", "")).strip(),
            fault_class=str(solution.get("fault_class", "")).strip(),
            affected_service=str(solution.get("affected_service", "")).strip(),
            action_type=str(solution.get("action_type", "")).strip(),
            confidence=float(solution.get("confidence", 0.0) or 0.0),
            evidence=list(solution.get("evidence", []) or []),
        )
        step = {
            "step": len(self.steps) + 1,
            "thought": "Diagnostic verifier approved final submit_solution.",
            "tool_called": "submit_solution",
            "call_id": output.get("call_id", ""),
            "inputs": {},
            "output": output,
            "timestamp": time.time(),
        }
        self._record_step(step)
        return step

    def _plan_follow_up_tools(self, hypotheses: Dict[str, Any], *, limit: int) -> List[Tuple[str, str]]:
        services = self._candidate_services(hypotheses)
        ranked = sorted(
            [dict(item or {}) for item in hypotheses.get("hypotheses", []) or []],
            key=lambda item: float(item.get("score", 0.0) or 0.0),
            reverse=True,
        )
        if ranked:
            top = ranked[0]
            missing = [str(item).strip() for item in top.get("missing_evidence", []) or [] if str(item).strip()]
            fault_class = str(top.get("fault_class", "")).strip()
            if float(top.get("score", 0.0) or 0.0) >= 0.75 and not missing and not self.ledger.missing_for_fault(fault_class):
                return []
        plausible = [item for item in ranked if float(item.get("score", 0.0) or 0.0) >= 0.45]
        if not plausible and ranked:
            plausible = ranked[:1]
        text = str({"hypotheses": plausible, "recommended_next_tools": hypotheses.get("recommended_next_tools", [])}).lower()
        planned: List[Tuple[str, str]] = []

        def add(tool: str, service: str) -> None:
            service = normalize_service_name(service or self._default_service())
            if len(planned) >= limit or self.ledger.seen(tool, service):
                return
            planned.append((tool, service))

        if (
            "dependency" in text
            or "native_bad_env" in text
            or "native_dependency_bad_endpoint" in text
            or "native_dependency_config_regression" in text
        ):
            add("get_dependency_traces", services[0])
            add("get_k8s_state", services[0])
        if any(token in text for token in ["resource", "cpu", "memory", "oom", "stress", "pressure"]):
            add("get_cluster_resource_context", services[0])
            add("get_metrics", services[0])
        if any(token in text for token in ["service_port", "service_selector", "wiring", "targetport", "selector"]):
            add("get_k8s_state", services[0])
        if any(token in text for token in ["probe", "image", "rollout", "pod_delete", "lifecycle"]):
            add("get_logs", services[0])
            add("get_k8s_state", services[0])
        if not planned and getattr(self.aci, "jaeger_enabled", False):
            add("get_dependency_traces", services[0])
        return planned

    def _plan_repair_tools(self, verification: Dict[str, Any], *, limit: int) -> List[Tuple[str, str]]:
        requested = dict(verification.get("next_tool", {}) or {})
        service = normalize_service_name(str(requested.get("service", "")).strip() or self._default_service())
        tool = str(requested.get("tool", "")).strip()
        planned: List[Tuple[str, str]] = []
        if tool in EVIDENCE_TOOLS and not self.ledger.seen(tool, service):
            planned.append((tool, service))
        if len(planned) < limit:
            for missing in list(verification.get("missing_evidence", []) or []):
                lowered = str(missing).lower()
                if "trace" in lowered and not self.ledger.seen("get_dependency_traces", service):
                    planned.append(("get_dependency_traces", service))
                elif "metric" in lowered and not self.ledger.seen("get_metrics", service):
                    planned.append(("get_metrics", service))
                elif "cluster" in lowered and not self.ledger.seen("get_cluster_resource_context", service):
                    planned.append(("get_cluster_resource_context", service))
                elif "k8s" in lowered and not self.ledger.seen("get_k8s_state", service):
                    planned.append(("get_k8s_state", service))
                if len(planned) >= limit:
                    break
        return planned[:limit]

    def _candidate_services(self, hypotheses: Dict[str, Any]) -> List[str]:
        candidates: List[str] = []

        def add(value: Any) -> None:
            service = normalize_service_name(str(value or "").strip())
            if service and service not in candidates:
                candidates.append(service)

        for service in hypotheses.get("affected_service_candidates", []) or []:
            add(service)
        for item in hypotheses.get("hypotheses", []) or []:
            add((item or {}).get("affected_service", ""))
        add(self._default_service())
        return candidates or ["frontend"]

    def _solution_from_verification(self, verification: Dict[str, Any]) -> Dict[str, Any]:
        raw_solution = verification.get("solution", {}) or {}
        solution = dict(raw_solution) if isinstance(raw_solution, dict) else {}
        if not solution:
            solution = {
                key: verification.get(key, "")
                for key in ["root_cause", "action_taken", "fault_class", "affected_service", "action_type", "confidence", "evidence"]
            }
        if solution.get("fault_class") == "unknown":
            solution["fault_class"] = ""
        if solution.get("action_type") == "unknown":
            solution["action_type"] = ""
        evidence = [str(item).strip() for item in list(solution.get("evidence", []) or []) if str(item).strip()]
        if not evidence:
            evidence = self.ledger.evidence_strings()[:8]
        solution["evidence"] = evidence
        solution["confidence"] = float(solution.get("confidence", 0.0) or 0.0)
        return solution

    def _verification_has_complete_supported_solution(self, verification: Dict[str, Any]) -> bool:
        raw_solution = verification.get("solution", {}) or {}
        solution = dict(raw_solution) if isinstance(raw_solution, dict) else {}
        fault_class = str(solution.get("fault_class", "") or verification.get("chosen_fault_class", "")).strip()
        if not fault_class or fault_class == "unknown":
            return False
        if self.ledger.missing_for_fault(fault_class):
            return False
        return bool(
            str(solution.get("root_cause", "")).strip()
            and str(solution.get("action_taken", "")).strip()
            and str(solution.get("affected_service", "")).strip()
            and str(solution.get("action_type", "")).strip()
        )

    def _record_step(self, step: Dict[str, Any]) -> None:
        self.steps.append(step)
        if self.step_callback is not None:
            self.step_callback(step)

    def _record_llm_event(self, name: str, output: Dict[str, Any]) -> None:
        event = {
            "step": len(self.steps) + 1,
            "name": name,
            "output": output,
            "timestamp": time.time(),
        }
        self.llm_events.append(event)
        self.steps.append(
            {
                "step": len(self.steps) + 1,
                "thought": f"Diagnostic controller completed {name}.",
                "tool_called": name,
                "call_id": str(uuid4()),
                "inputs": {},
                "output": output,
                "timestamp": event["timestamp"],
            }
        )

    def _default_service(self) -> str:
        for service in self._initial_context.get("suspicious_services", []) or []:
            cleaned = normalize_service_name(str(service))
            if cleaned:
                return cleaned
        for finding in self._initial_context.get("critical_findings", []) or []:
            cleaned = normalize_service_name(str((finding or {}).get("service", "")))
            if cleaned:
                return cleaned
        return "frontend"

    @staticmethod
    def _tool_inputs(tool: str, service: str) -> Dict[str, Any]:
        inputs: Dict[str, Any] = {"service": service}
        if tool in {"get_metrics", "get_traces", "get_dependency_traces"}:
            inputs["lookback_minutes"] = 5
        if tool == "get_dependency_traces":
            inputs["entry_service"] = "frontend"
        if tool == "get_logs":
            inputs["tail_lines"] = 100
        return inputs

    @staticmethod
    def _hypothesis_schema() -> Dict[str, Any]:
        candidate = {
            "type": "object",
            "properties": {
                "fault_class": {"type": "string", "enum": FAULT_CLASSES},
                "category": {"type": "string", "enum": DIAGNOSIS_CATEGORIES},
                "affected_service": {"type": "string"},
                "supporting_evidence": {"type": "array", "items": {"type": "string"}},
                "contradicting_evidence": {"type": "array", "items": {"type": "string"}},
                "missing_evidence": {"type": "array", "items": {"type": "string"}},
                "score": {"type": "number"},
            },
            "required": [
                "fault_class",
                "category",
                "affected_service",
                "supporting_evidence",
                "contradicting_evidence",
                "missing_evidence",
                "score",
            ],
            "additionalProperties": False,
        }
        return {
            "type": "object",
            "properties": {
                "symptom_scope": {"type": "string"},
                "affected_service_candidates": {"type": "array", "items": {"type": "string"}},
                "hypotheses": {"type": "array", "items": candidate},
                "distinguishing_question": {"type": "string"},
                "recommended_next_tools": {
                    "type": "array",
                    "items": {"type": "string", "enum": sorted(EVIDENCE_TOOLS)},
                },
            },
            "required": [
                "symptom_scope",
                "affected_service_candidates",
                "hypotheses",
                "distinguishing_question",
                "recommended_next_tools",
            ],
            "additionalProperties": False,
        }

    @staticmethod
    def _verifier_schema() -> Dict[str, Any]:
        solution = {
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
        next_tool = {
            "type": "object",
            "properties": {
                "tool": {"type": "string", "enum": sorted(EVIDENCE_TOOLS) + ["none"]},
                "service": {"type": "string"},
            },
            "required": ["tool", "service"],
            "additionalProperties": False,
        }
        return {
            "type": "object",
            "properties": {
                "ready_to_submit": {"type": "boolean"},
                "chosen_fault_class": {"type": "string", "enum": FAULT_CLASSES},
                "why_this_class": {"type": "string"},
                "why_not_nearest_alternative": {"type": "string"},
                "missing_evidence": {"type": "array", "items": {"type": "string"}},
                "next_tool": next_tool,
                "solution": solution,
            },
            "required": [
                "ready_to_submit",
                "chosen_fault_class",
                "why_this_class",
                "why_not_nearest_alternative",
                "missing_evidence",
                "next_tool",
                "solution",
            ],
            "additionalProperties": False,
        }
