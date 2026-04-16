from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from agent_graph.aci import AgentCloudInterface
from agent_graph.react_support import (
    BAD_ROLLOUT_MARKERS,
    CONNECTION_ERROR_MARKERS,
    MAX_SEARCH_GUARDRAIL_ATTEMPTS,
    RATE_LIMIT_SECONDS,
    RESOURCE_PRESSURE_MARKERS,
    SERVICE_TOPOLOGY,
    collect_output_text,
    default_model,
    dominant_trace_link,
    extract_markers,
    metrics_signal_summary,
    normalize_provider,
    normalize_service_name,
    service_unavailable,
)
from agent_graph.react_prompt import PURE_SYSTEM_PROMPT
from agent_graph.react_render import format_thought, summarize_output, summarize_output_for_prompt, tool_signatures
from agent_graph.reasoning.llm import ResponsesJSONClient

class ReActAgent:
    def __init__(
        self,
        aci: AgentCloudInterface,
        provider: str | None = None,
        model: str | None = None,
        max_steps: int = 35,
        allow_exec_shell: bool = True,
        diagnosis_only: bool = False,
        step_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.aci = aci
        self.provider = normalize_provider(provider or os.environ.get("LLM_PROVIDER", "openai"))
        self.model = model or default_model(self.provider)
        self.max_steps = max_steps
        self.allow_exec_shell = allow_exec_shell
        self.diagnosis_only = diagnosis_only
        self.step_callback = step_callback
        self.client = ResponsesJSONClient(model=self.model, provider=self.provider)
        self.trace: List[Dict[str, Any]] = []
        self._decision_history: List[Dict[str, Any]] = []
        self._initial_context: Dict[str, Any] = {}
        self.guardrail_events: List[Dict[str, Any]] = []
        self._last_llm_call_at: float | None = None
        if not self.client.available():
            raise RuntimeError(f"LLM provider '{self.provider}' is not configured")

    def run(self, problem_description: str, initial_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.trace = []
        self._decision_history = []
        self._initial_context = initial_context or {}
        self.guardrail_events = []

        for step_number in range(1, self.max_steps + 1):
            allowed_tools = self._allowed_tools(step_number)
            prompt = self._build_prompt(problem_description, step_number, allowed_tools)
            decision = self._decide_with_guardrails(prompt, allowed_tools)
            step_record = self._execute_step(step_number, decision)
            self.trace.append(step_record)
            self._decision_history.append(
                {
                    "step": step_number,
                    "thought": step_record["thought"],
                    "tool_called": step_record["tool_called"],
                    "call_id": step_record["call_id"],
                    "summary": summarize_output_for_prompt(step_record["output"]),
                }
            )
            if self.step_callback is not None:
                self.step_callback(step_record)

            if step_record["tool_called"] == "submit_solution":
                output = step_record["output"]
                if output.get("solution_logged") and not output.get("error") and output.get("evidence_valid", True):
                    return {
                        "agent_type": "react",
                        "provider": self.provider,
                        "model": self.model,
                        "agent_variant": "pure_react",
                        "guardrail_events": list(self.guardrail_events),
                        "steps": list(self.trace),
                        "solution": output,
                    }
                continue

        raise RuntimeError("ReAct agent reached max_steps without submitting a valid solution")

    def _allowed_tools(self, step_number: int) -> List[str]:
        evidence_calls = [step for step in self.trace if step["tool_called"] != "submit_solution"]
        tool_names = [step["tool_called"] for step in self.trace]

        if not tool_names:
            return ["get_k8s_state"]

        allowed = ["get_k8s_state", "get_metrics", "get_logs"]
        if self.aci.jaeger_enabled:
            allowed.extend(["get_traces", "get_dependency_traces"])
        if len(evidence_calls) >= 2 and not self.diagnosis_only:
            allowed.extend(
                [
                    "restart_pod",
                    "rollout_restart",
                    "rollout_undo",
                    "patch_resources",
                    "wait_and_monitor",
                ]
            )

        if len(evidence_calls) >= 2:
            allowed.append("submit_solution")

        if step_number >= self.max_steps and "submit_solution" in allowed:
            return ["submit_solution"]

        return allowed

    def _build_prompt(self, problem_description: str, step_number: int, allowed_tools: List[str]) -> Dict[str, Any]:
        return {
            "system_prompt": PURE_SYSTEM_PROMPT,
            "task": problem_description,
            "provider": self.provider,
            "model": self.model,
            "jaeger_enabled": self.aci.jaeger_enabled,
            "diagnosis_only": self.diagnosis_only,
            "step_number": step_number,
            "max_steps": self.max_steps,
            "available_tools": tool_signatures(allowed_tools),
            "service_topology": SERVICE_TOPOLOGY,
            "initial_observations": self._initial_context,
            "focus_services": self._focus_services(),
            "evidence_ledger": self._current_evidence_ledger(),
            "observability_hints": {
                "currently_unavailable_services": self._currently_unavailable_services(),
                "recent_stalled_tool_types": self._recent_stalled_tool_types(),
            },
            "constraints": {
                "must_call_get_k8s_state_first": True,
                "minimum_evidence_calls_before_submit": 2,
                "must_call_get_traces_before_blaming_downstream_dependency_if_latency_related": self.aci.jaeger_enabled,
                "must_cite_real_call_ids": True,
                "must_not_assume_fault_without_retrieved_evidence": True,
                "must_avoid_repeating_the_same_target_without_new_signal": True,
                "must_not_repeat_the_same_evidence_question_without_time_based_change": True,
                "prefer_metrics_before_repeated_logs_for_healthy_but_slow_services": True,
                "must_use_typed_action_tools_instead_of_raw_shell": True,
                "must_not_execute_remediation_tools_in_diagnosis_only_mode": self.diagnosis_only,
            },
            "completed_steps": list(self._decision_history),
            "available_call_ids": [step["call_id"] for step in self.trace if step["tool_called"] != "submit_solution"],
        }

    def _build_retry_prompt(
        self,
        base_prompt: Dict[str, Any],
        allowed_tools: List[str],
        violation: Dict[str, Any],
    ) -> Dict[str, Any]:
        prompt = dict(base_prompt)
        prompt["available_tools"] = tool_signatures(allowed_tools)
        prompt["guardrail_feedback"] = violation
        return prompt

    def _decide(self, prompt: Dict[str, Any], allowed_tools: List[str]) -> Dict[str, Any]:
        base_required_fields = [
            "belief",
            "uncertainty",
            "next_evidence_needed",
            "leading_hypothesis",
            "alternative_hypothesis",
            "evidence_supporting_leading",
            "evidence_against_alternative",
            "what_result_would_change_my_mind",
            "decision_impact",
            "why_this_tool_reduces_uncertainty",
            "why_not_submit_now",
            "tool",
            "tool_input",
        ]
        all_properties = [
            "belief",
            "uncertainty",
            "next_evidence_needed",
            "leading_hypothesis",
            "alternative_hypothesis",
            "evidence_supporting_leading",
            "evidence_against_alternative",
            "what_result_would_change_my_mind",
            "decision_impact",
            "why_this_tool_reduces_uncertainty",
            "why_not_submit_now",
            "tool",
            "tool_input",
            "root_cause",
            "action_taken",
            "fault_class",
            "affected_service",
            "action_type",
            "confidence",
            "evidence",
        ]
        tool_input_schema = self._tool_input_schema()
        required_fields = list(all_properties) if self.provider == "openai" else list(base_required_fields)
        self._rate_limit()
        parsed = self.client.complete_json(
            name="react_step",
            schema={
                "type": "object",
                "properties": {
                    "belief": {"type": "string"},
                    "uncertainty": {"type": "string"},
                    "next_evidence_needed": {"type": "string"},
                    "leading_hypothesis": {"type": "string"},
                    "alternative_hypothesis": {"type": "string"},
                    "evidence_supporting_leading": {"type": "string"},
                    "evidence_against_alternative": {"type": "string"},
                    "what_result_would_change_my_mind": {"type": "string"},
                    "decision_impact": {"type": "string"},
                    "why_this_tool_reduces_uncertainty": {"type": "string"},
                    "why_not_submit_now": {"type": "string"},
                    "tool": {"type": "string", "enum": allowed_tools},
                    "tool_input": tool_input_schema,
                    "root_cause": {"type": "string"},
                    "action_taken": {"type": "string"},
                    "fault_class": {
                        "type": "string",
                        "enum": [
                            "unknown",
                            "capacity_regression",
                            "compound_incident",
                            "dependency_localization",
                            "observability_challenge",
                            "partial_degradation",
                            "pod_disturbance",
                            "replay_benchmark",
                            "resource_pressure",
                            "runtime_failure",
                            "rollout_failure",
                            "native_service_selector_mismatch",
                            "native_service_port_mismatch",
                            "native_bad_image_rollout",
                            "native_bad_probe_rollout",
                            "native_bad_env",
                            "native_scale_zero",
                            "native_pod_delete",
                            "native_dependency_bad_endpoint",
                            "native_cpu_limit_throttle",
                            "native_memory_limit_oom",
                            "native_cpu_pressure_stress_job",
                            "native_memory_pressure_stress_job",
                        ],
                    },
                    "affected_service": {"type": "string"},
                    "action_type": {
                        "type": "string",
                        "enum": [
                            "unknown",
                            "rollout_undo",
                            "rollout_restart",
                            "restart_pod",
                            "patch_resources",
                            "patch_resources_then_scale",
                            "patch_service_selector",
                            "patch_service_target_port",
                            "scale_deployment",
                            "wait_and_monitor",
                        ],
                    },
                    "confidence": {"type": "number"},
                    "evidence": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": required_fields,
                "additionalProperties": False,
            },
            prompt=prompt,
        )
        self._last_llm_call_at = time.time()
        return parsed

    def _tool_input_schema(self) -> Dict[str, Any]:
        base_properties: Dict[str, Any] = {
            "service": {"type": "string"},
            "entry_service": {"type": "string"},
            "lookback_minutes": {"type": "integer"},
            "tail_lines": {"type": "integer"},
            "pod_name": {"type": "string"},
            "cpu": {"type": "string"},
            "cpu_request": {"type": "string"},
            "cpu_limit": {"type": "string"},
            "memory_request": {"type": "string"},
            "memory_limit": {"type": "string"},
            "container": {"type": "string"},
            "seconds": {"type": "integer"},
            "command": {"type": "string"},
        }
        schema: Dict[str, Any] = {
            "type": "object",
            "properties": base_properties,
            "additionalProperties": False,
        }
        if self.provider == "openai":
            schema["required"] = list(base_properties.keys())
        return schema

    def _decide_with_guardrails(self, prompt: Dict[str, Any], allowed_tools: List[str]) -> Dict[str, Any]:
        retry_allowed_tools = list(allowed_tools)
        retry_prompt = prompt
        for attempt in range(MAX_SEARCH_GUARDRAIL_ATTEMPTS):
            decision = self._decide(retry_prompt, retry_allowed_tools)
            violation = self._decision_guardrail_violation(decision)
            if violation is None:
                return decision

            violation_record = {
                "step": len(self.trace) + 1,
                "attempt": attempt + 1,
                "type": str(violation.get("type", "")),
                "reason": str(violation.get("reason", "")),
                "decision": {
                    "tool": str(decision.get("tool", "")),
                    "tool_input": dict(decision.get("tool_input", {}) or {}),
                },
            }
            self.guardrail_events.append(violation_record)

            disallow_tool = str(violation.get("disallow_tool", "")).strip()
            if disallow_tool and disallow_tool in retry_allowed_tools and len(retry_allowed_tools) > 1:
                narrowed = [tool for tool in retry_allowed_tools if tool != disallow_tool]
                if narrowed:
                    retry_allowed_tools = narrowed

            retry_prompt = self._build_retry_prompt(
                prompt,
                retry_allowed_tools,
                {
                    **violation,
                    "attempt": attempt + 1,
                    "previous_decision": violation_record["decision"],
                    "instruction": "Choose a different valid next step that reduces uncertainty.",
                },
            )

        raise RuntimeError(
            "ReAct agent failed to produce a valid next tool call after repeated search-guardrail rejections"
        )

    def _execute_step(self, step_number: int, decision: Dict[str, Any]) -> Dict[str, Any]:
        tool = str(decision.get("tool", "")).strip()
        tool_input = dict(decision.get("tool_input", {}) or {})
        thought = format_thought(decision)
        service = ""

        if tool in {"get_k8s_state", "get_metrics", "get_traces", "get_dependency_traces", "get_logs"}:
            service = self._resolve_service(tool, tool_input)
            tool_input["service"] = service
        elif tool in {"restart_pod", "rollout_restart", "rollout_undo", "patch_resources"}:
            service = self._resolve_service("get_k8s_state", tool_input)
            tool_input["service"] = service

        output: Dict[str, Any]
        if tool == "get_k8s_state":
            output = self.aci.get_k8s_state(service)
        elif tool == "get_metrics":
            output = self.aci.get_metrics(
                service,
                lookback_minutes=int(tool_input.get("lookback_minutes", 5) or 5),
            )
        elif tool == "get_traces":
            output = self.aci.get_traces(
                service,
                lookback_minutes=int(tool_input.get("lookback_minutes", 5) or 5),
            )
        elif tool == "get_dependency_traces":
            output = self.aci.get_dependency_traces(
                service,
                entry_service=str(tool_input.get("entry_service", "frontend")).strip() or "frontend",
                lookback_minutes=int(tool_input.get("lookback_minutes", 5) or 5),
            )
        elif tool == "get_logs":
            output = self.aci.get_logs(
                service,
                tail_lines=int(tool_input.get("tail_lines", 100) or 100),
            )
        elif tool == "restart_pod":
            output = self.aci.restart_pod(
                service,
                pod_name=str(tool_input.get("pod_name", "")).strip(),
            )
        elif tool == "rollout_restart":
            output = self.aci.rollout_restart(service)
        elif tool == "rollout_undo":
            output = self.aci.rollout_undo(service)
        elif tool == "patch_resources":
            cpu = str(tool_input.get("cpu", "")).strip()
            output = self.aci.patch_resources(
                service,
                cpu_request=str(tool_input.get("cpu_request", "")).strip() or cpu,
                cpu_limit=str(tool_input.get("cpu_limit", "")).strip() or cpu,
                memory_request=str(tool_input.get("memory_request", "")).strip(),
                memory_limit=str(tool_input.get("memory_limit", "")).strip(),
                container=str(tool_input.get("container", "server")).strip() or "server",
            )
        elif tool == "wait_and_monitor":
            output = self.aci.wait_and_monitor(
                seconds=int(tool_input.get("seconds", 30) or 30),
            )
        elif tool == "exec_shell":
            output = self.aci.exec_shell(str(tool_input.get("command", "")).strip())
        elif tool == "submit_solution":
            root_cause = str(decision.get("root_cause", "")).strip()
            action_taken = str(decision.get("action_taken", "")).strip()
            fault_class = str(decision.get("fault_class", "")).strip()
            affected_service = str(decision.get("affected_service", "")).strip()
            action_type = str(decision.get("action_type", "")).strip()
            if fault_class == "unknown":
                fault_class = ""
            if action_type == "unknown":
                action_type = ""
            confidence = float(decision.get("confidence", 0.0) or 0.0)
            evidence = [str(item).strip() for item in list(decision.get("evidence", []) or []) if str(item).strip()]
            if confidence <= 0.0 and (root_cause or action_taken):
                confidence = 0.5
            output = self.aci.submit_solution(
                root_cause=root_cause,
                action_taken=action_taken,
                fault_class=fault_class,
                affected_service=affected_service,
                action_type=action_type,
                confidence=confidence,
                evidence=evidence,
            )
        else:
            output = {
                "call_id": "",
                "timestamp": time.time(),
                "error": f"unsupported tool selected: {tool}",
            }

        return {
            "step": step_number,
            "thought": thought,
            "tool_called": tool,
            "call_id": output.get("call_id", ""),
            "inputs": tool_input,
            "output": output,
            "timestamp": time.time(),
        }

    def _resolve_service(self, tool: str, tool_input: Dict[str, Any]) -> str:
        requested = str(tool_input.get("service", "")).strip()
        return requested or self._default_service()

    def _decision_guardrail_violation(self, decision: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        tool = str(decision.get("tool", "")).strip()
        if tool in {"", "submit_solution"}:
            return None

        tool_input = dict(decision.get("tool_input", {}) or {})
        candidate_service = self._candidate_service(tool, tool_input)
        signature = self._tool_call_signature(tool, tool_input, candidate_service)
        if self._has_seen_signature(signature):
            return {
                "type": "duplicate_call",
                "reason": (
                    f"The candidate call {tool} on {candidate_service or 'global scope'} with the same arguments "
                    "already happened in this run. Choose a different tool or target that reduces uncertainty."
                ),
                "disallow_tool": tool,
            }

        if tool in {"get_traces", "get_dependency_traces"} and candidate_service and self._service_is_currently_unavailable(candidate_service):
            return {
                "type": "down_service_trace",
                "reason": (
                    f"{candidate_service} is currently unavailable. Traces on that same unavailable service are low-yield. "
                    "Prefer logs, Kubernetes state, or traces from an upstream entry point."
                ),
                "disallow_tool": tool,
            }

        if (
            tool == "get_metrics"
            and candidate_service
            and self._service_is_currently_unavailable(candidate_service)
            and self._latest_step("get_logs", candidate_service) is None
        ):
            return {
                "type": "unavailable_service_metrics",
                "reason": (
                    f"{candidate_service} is currently unavailable and logs have not been inspected yet. "
                    "Metrics on that same unavailable service are usually less discriminative than logs or Kubernetes events."
                ),
                "disallow_tool": "get_metrics",
            }

        stalled_tools = self._recent_stalled_tool_types()
        if stalled_tools and tool in stalled_tools:
            return {
                "type": "stalled_tool_type",
                "reason": (
                    f"The last two evidence calls added no new signal, and {tool} was already part of that stalled pattern. "
                    "Choose a different tool type."
                ),
                "disallow_tool": tool,
            }

        return None

    def _default_service(self) -> str:
        focus_services = self._focus_services()
        if focus_services:
            return focus_services[0]
        return "frontend"

    def _candidate_service(self, tool: str, tool_input: Dict[str, Any]) -> str:
        if tool in {
            "get_k8s_state",
            "get_metrics",
            "get_traces",
            "get_dependency_traces",
            "get_logs",
            "restart_pod",
            "rollout_restart",
            "rollout_undo",
            "patch_resources",
        }:
            requested = str(tool_input.get("service", "")).strip()
            if requested:
                return normalize_service_name(requested)
            return normalize_service_name(self._default_service())
        return ""

    def _focus_services(self) -> List[str]:
        candidates: List[str] = []

        def add(service: str) -> None:
            cleaned = service.strip()
            if cleaned and cleaned not in candidates:
                candidates.append(cleaned)

        for service in self._initial_context.get("suspicious_services", []) or []:
            add(str(service))

        for finding in self._initial_context.get("critical_findings", []) or []:
            add(str((finding or {}).get("service", "")))

        for step in self.trace:
            output = step.get("output", {}) or {}
            service = str(output.get("service", "")).strip()
            desired = int(output.get("desired_replicas", 0) or 0)
            available = int(output.get("available_replicas", 0) or 0)
            if service and desired > available:
                add(service)
            if service and bool(output.get("rollout_progressing", False)):
                add(service)
            if service and int(output.get("error_count", 0) or 0) > 0:
                add(service)

            bottleneck_service = str(output.get("bottleneck_service", "")).strip()
            if bottleneck_service and bottleneck_service != "frontend":
                add(bottleneck_service)

            for error_span in output.get("error_spans", []) or []:
                add(str((error_span or {}).get("service", "")))

        return candidates

    def _current_evidence_ledger(self) -> List[Dict[str, Any]]:
        ledger: List[Dict[str, Any]] = []
        for step in self._evidence_steps()[-6:]:
            output = step.get("output", {}) or {}
            ledger.append(
                {
                    "tool": str(step.get("tool_called", "")),
                    "service": normalize_service_name(
                        str((step.get("inputs", {}) or {}).get("service", "")).strip()
                        or str(output.get("service", "")).strip()
                    ),
                    "summary": summarize_output_for_prompt(output),
                }
            )
        return ledger

    def _tool_call_signature(
        self,
        tool: str,
        tool_input: Dict[str, Any],
        service: str = "",
    ) -> Tuple[str, Tuple[Tuple[str, Any], ...]]:
        normalized: Dict[str, Any] = {}
        if service:
            normalized["service"] = service

        if tool in {"get_metrics", "get_traces"}:
            normalized["lookback_minutes"] = int(tool_input.get("lookback_minutes", 5) or 5)
        elif tool == "get_dependency_traces":
            normalized["lookback_minutes"] = int(tool_input.get("lookback_minutes", 5) or 5)
            normalized["entry_service"] = str(tool_input.get("entry_service", "frontend")).strip() or "frontend"
        elif tool == "get_logs":
            normalized["tail_lines"] = int(tool_input.get("tail_lines", 100) or 100)
        elif tool == "restart_pod":
            normalized["pod_name"] = str(tool_input.get("pod_name", "")).strip()
        elif tool == "patch_resources":
            normalized["cpu_request"] = str(tool_input.get("cpu_request", "")).strip() or str(tool_input.get("cpu", "")).strip()
            normalized["cpu_limit"] = str(tool_input.get("cpu_limit", "")).strip() or str(tool_input.get("cpu", "")).strip()
            normalized["memory_request"] = str(tool_input.get("memory_request", "")).strip()
            normalized["memory_limit"] = str(tool_input.get("memory_limit", "")).strip()
            normalized["container"] = str(tool_input.get("container", "server")).strip() or "server"
        elif tool == "wait_and_monitor":
            normalized["seconds"] = int(tool_input.get("seconds", 30) or 30)

        return tool, tuple(sorted(normalized.items()))

    def _has_seen_signature(self, signature: Tuple[str, Tuple[Tuple[str, Any], ...]]) -> bool:
        for step in self._evidence_steps():
            prior_tool = str(step.get("tool_called", "")).strip()
            prior_inputs = dict(step.get("inputs", {}) or {})
            prior_service = self._candidate_service(prior_tool, prior_inputs)
            if self._tool_call_signature(prior_tool, prior_inputs, prior_service) == signature:
                return True
        return False

    def _service_is_currently_unavailable(self, service: str) -> bool:
        k8s_step = self._latest_step("get_k8s_state", service)
        if k8s_step is None:
            return False
        return service_unavailable(k8s_step.get("output", {}) or {})

    def _currently_unavailable_services(self) -> List[str]:
        unavailable: List[str] = []
        for service in self._services_with_evidence():
            if self._service_is_currently_unavailable(service):
                unavailable.append(service)
        return unavailable

    def _recent_stalled_tool_types(self) -> List[str]:
        evidence_steps = self._evidence_steps()
        if len(evidence_steps) < 2:
            return []
        novelty_flags = [self._step_adds_new_signal(evidence_steps[:index], step) for index, step in enumerate(evidence_steps)]
        if novelty_flags[-1] or novelty_flags[-2]:
            return []
        stalled = []
        for step in evidence_steps[-2:]:
            tool = str(step.get("tool_called", "")).strip()
            if tool and tool not in stalled:
                stalled.append(tool)
        return stalled

    def _evidence_steps(self) -> List[Dict[str, Any]]:
        return [step for step in self.trace if step.get("tool_called") != "submit_solution"]

    def _steps_for_tool(self, tool: str) -> List[Dict[str, Any]]:
        return [step for step in self._evidence_steps() if step.get("tool_called") == tool]

    def _latest_step(self, tool: str, service: str) -> Optional[Dict[str, Any]]:
        normalized = normalize_service_name(service)
        for step in reversed(self._evidence_steps()):
            if step.get("tool_called") != tool:
                continue
            step_service = normalize_service_name(
                str((step.get("inputs", {}) or {}).get("service", "")).strip()
                or str((step.get("output", {}) or {}).get("service", "")).strip()
            )
            if step_service == normalized:
                return step
        return None

    def _services_with_evidence(self) -> List[str]:
        candidates: List[str] = []
        for step in self._evidence_steps():
            service = normalize_service_name(
                str((step.get("inputs", {}) or {}).get("service", "")).strip()
                or str((step.get("output", {}) or {}).get("service", "")).strip()
            )
            if service and service not in candidates:
                candidates.append(service)
        for service in self._focus_services():
            normalized = normalize_service_name(service)
            if normalized and normalized not in candidates:
                candidates.append(normalized)
        return candidates

    def _diagnostic_tokens(self, step: Dict[str, Any]) -> set[str]:
        tool = str(step.get("tool_called", "")).strip()
        output = step.get("output", {}) or {}
        service = normalize_service_name(
            str((step.get("inputs", {}) or {}).get("service", "")).strip()
            or str(output.get("service", "")).strip()
        )
        tokens: set[str] = set()
        if service:
            tokens.add(f"service:{service}")

        text = collect_output_text(output).lower()
        if tool == "get_k8s_state":
            tokens.add(f"availability:{int(output.get('available_replicas', 0) or 0)}/{int(output.get('desired_replicas', 0) or 0)}")
            tokens.add(f"rollout:{bool(output.get('rollout_progressing', False))}")
            tokens.add(f"restart:{int(output.get('restart_count', 0) or 0)}")
            for pod in output.get("pod_phases", []) or []:
                tokens.add(
                    "pod:"
                    + ":".join(
                        [
                            str((pod or {}).get("phase", "")),
                            str(bool((pod or {}).get("ready", False))),
                            str(int((pod or {}).get("restart_count", 0) or 0)),
                        ]
                    )
                )
        elif tool == "get_logs":
            tokens.add(f"log_error_count:{int(output.get('error_count', 0) or 0)}")
        elif tool == "get_metrics":
            metrics = output.get("metrics", {}) or {}
            tokens.add(f"cpu_band:{round(float(metrics.get('cpu_usage', 0.0) or 0.0), 2)}")
            tokens.add(f"error_rate_band:{round(float(metrics.get('error_rate', 0.0) or 0.0), 2)}")
            tokens.add(f"latency_band:{round(float(metrics.get('p99_latency_ms', 0.0) or 0.0), -1)}")
        elif tool == "get_traces":
            tokens.add(f"trace_count:{int(output.get('trace_count', 0) or 0)}")
            bottleneck = normalize_service_name(str(output.get("bottleneck_service", "")))
            if bottleneck:
                tokens.add(f"bottleneck:{bottleneck}")
            dominant = dominant_trace_link(output)
            if dominant is not None:
                tokens.add(f"link:{dominant['caller']}->{dominant['callee']}")
                tokens.add(f"link_pct:{round(float(dominant['pct_of_total']), 2)}")

        for marker in BAD_ROLLOUT_MARKERS:
            if marker in text:
                tokens.add(f"marker:{marker}")
        for marker in CONNECTION_ERROR_MARKERS:
            if marker in text:
                tokens.add(f"marker:{marker}")
        for marker in RESOURCE_PRESSURE_MARKERS:
            if marker in text:
                tokens.add(f"marker:{marker}")
        return tokens

    def _step_adds_new_signal(self, prior_steps: List[Dict[str, Any]], step: Dict[str, Any]) -> bool:
        current_tokens = self._diagnostic_tokens(step)
        prior_tokens: set[str] = set()
        for prior in prior_steps:
            prior_tokens |= self._diagnostic_tokens(prior)
        return bool(current_tokens - prior_tokens)

    def _rate_limit(self) -> None:
        if self._last_llm_call_at is None:
            return
        sleep_seconds = RATE_LIMIT_SECONDS.get(self.provider, 0)
        if sleep_seconds <= 0:
            return
        elapsed = time.time() - self._last_llm_call_at
        if elapsed < sleep_seconds:
            time.sleep(sleep_seconds - elapsed)
