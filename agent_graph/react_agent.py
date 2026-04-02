from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from agent_graph.aci import AgentCloudInterface
from agent_graph.reasoning.llm import ResponsesJSONClient


DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
    "gemini": "gemini-2.5-flash",
    "ollama": "llama3",
}

RATE_LIMIT_SECONDS = {
    "anthropic": 15,
    "openai": 15,
    "gemini": 20,
    "ollama": 0,
}

SERVICE_TOPOLOGY = {
    "frontend": ["productcatalogservice", "currencyservice", "cartservice", "recommendationservice", "checkoutservice"],
    "cartservice": ["redis-cart"],
    "productcatalogservice": [],
    "checkoutservice": ["cartservice", "productcatalogservice", "paymentservice", "currencyservice", "emailservice", "shippingservice"],
    "paymentservice": [],
    "currencyservice": [],
    "recommendationservice": ["productcatalogservice"],
    "shippingservice": [],
    "redis-cart": [],
}

BAD_ROLLOUT_MARKERS = (
    "imagepullbackoff",
    "errimagepull",
    "manifest unknown",
    "failed to pull image",
    "trying and failing to pull image",
    "image can't be pulled",
    "crashloopbackoff",
)

CONNECTION_ERROR_MARKERS = (
    "connection refused",
    "context deadline exceeded",
    "deadline exceeded",
    "i/o timeout",
    "timed out",
    "transport is closing",
    "unavailable",
)

RESOURCE_PRESSURE_MARKERS = (
    "oomkill",
    "oom killed",
    "out of memory",
    "throttl",
    "cpu cfs quota",
    "resource temporarily unavailable",
)

MAX_SEARCH_GUARDRAIL_ATTEMPTS = 6


class ReActAgent:
    def __init__(
        self,
        aci: AgentCloudInterface,
        provider: str | None = None,
        model: str | None = None,
        max_steps: int = 35,
        allow_exec_shell: bool = True,
        step_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.aci = aci
        self.provider = self._normalize_provider(provider or os.environ.get("LLM_PROVIDER", "openai"))
        self.model = model or self._default_model(self.provider)
        self.max_steps = max_steps
        self.allow_exec_shell = allow_exec_shell
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
                    "summary": self._summarize_output_for_prompt(step_record["output"]),
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
        if len(evidence_calls) >= 2:
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
            "system_prompt": self._system_prompt(),
            "task": problem_description,
            "provider": self.provider,
            "model": self.model,
            "jaeger_enabled": self.aci.jaeger_enabled,
            "step_number": step_number,
            "max_steps": self.max_steps,
            "available_tools": self._tool_signatures(allowed_tools),
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
                "must_use_typed_action_tools_instead_of_raw_shell": True,
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
        prompt["available_tools"] = self._tool_signatures(allowed_tools)
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
        thought = self._format_thought(decision)
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
            root_cause, action_taken, confidence, evidence = self._prepare_submission(decision)
            output = self.aci.submit_solution(
                root_cause=root_cause,
                action_taken=action_taken,
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

    def _format_thought(self, decision: Dict[str, Any]) -> str:
        belief = str(decision.get("belief", "")).strip()
        uncertainty = str(decision.get("uncertainty", "")).strip()
        next_evidence = str(decision.get("next_evidence_needed", "")).strip()
        parts = [f"Belief: {belief}"]
        leading = str(decision.get("leading_hypothesis", "")).strip()
        alternative = str(decision.get("alternative_hypothesis", "")).strip()
        support = str(decision.get("evidence_supporting_leading", "")).strip()
        mind_change = str(decision.get("what_result_would_change_my_mind", "")).strip()
        impact = str(decision.get("decision_impact", "")).strip()
        why = str(decision.get("why_this_tool_reduces_uncertainty", "")).strip()
        if leading:
            if alternative:
                parts.append(f"Hypotheses: {leading} vs {alternative}")
            else:
                parts.append(f"Hypothesis: {leading}")
        if support:
            parts.append(f"Support: {support}")
        parts.append(f"Uncertainty: {uncertainty}")
        parts.append(f"Next evidence: {next_evidence}")
        if impact:
            parts.append(f"Decision impact: {impact}")
        if mind_change:
            parts.append(f"Would change my mind if: {mind_change}")
        if why:
            parts.append(f"Why: {why}")
        return " | ".join(parts)

    def _summarize_output(self, output: Dict[str, Any]) -> Dict[str, Any]:
        summary = self._summarize_output_for_prompt(output)
        if "call_chain" in output:
            summary["call_chain_hops"] = len(output.get("call_chain", []) or [])
        if "error_spans" in output:
            summary["error_span_count"] = len(output.get("error_spans", []) or [])
        if "recent_events" in output:
            summary["recent_event_count"] = len(output.get("recent_events", []) or [])
        if "pod_phases" in output:
            summary["pod_count"] = len(output.get("pod_phases", []) or [])
        return summary

    def _summarize_output_for_prompt(self, output: Dict[str, Any]) -> Dict[str, Any]:
        summary: Dict[str, Any] = {}
        scalar_keys = [
            "service",
            "entry_point",
            "entry_service",
            "trace_count",
            "focus_trace_count",
            "raw_trace_count",
            "application_trace_count",
            "bottleneck_service",
            "bottleneck_pct_of_total",
            "deviation_factor",
            "summary",
            "error_count",
            "pod_name",
            "desired_replicas",
            "available_replicas",
            "rollout_progressing",
            "restart_count",
            "exit_code",
            "solution_logged",
            "root_cause",
            "action_taken",
            "evidence_valid",
        ]
        for key in scalar_keys:
            if key in output:
                summary[key] = output.get(key)

        error_value = output.get("error")
        if error_value:
            summary["error"] = self._truncate(str(error_value), 160)

        recent_events = output.get("recent_events", []) or []
        if recent_events:
            ranked_events = sorted(
                recent_events,
                key=lambda item: (
                    0 if str((item or {}).get("type", "")).lower() == "warning" else 1,
                    0 if "fail" in str((item or {}).get("reason", "")).lower() else 1,
                    0 if "backoff" in str((item or {}).get("reason", "")).lower() else 1,
                ),
            )
            summary["recent_events"] = [
                {
                    "reason": str(item.get("reason", "")),
                    "object": str(item.get("object", "")),
                    "type": str(item.get("type", "")),
                    "message": self._truncate(str(item.get("message", "")), 120),
                }
                for item in ranked_events[:4]
            ]

        pod_phases = output.get("pod_phases", []) or []
        if pod_phases:
            summary["pod_phases"] = [
                {
                    "pod_name": str(item.get("pod_name", "")),
                    "phase": str(item.get("phase", "")),
                    "ready": bool(item.get("ready", False)),
                    "restart_count": int(item.get("restart_count", 0) or 0),
                }
                for item in pod_phases[:3]
            ]
        if "desired_replicas" in output or "available_replicas" in output:
            desired = int(output.get("desired_replicas", 0) or 0)
            available = int(output.get("available_replicas", 0) or 0)
            summary["availability_gap"] = f"{available}/{desired}"

        output_text = self._collect_output_text(output).lower()
        startup_markers = self._extract_markers(output_text, BAD_ROLLOUT_MARKERS)
        if startup_markers:
            summary["startup_failure_markers"] = startup_markers[:4]

        metrics = output.get("metrics", {}) or {}
        if metrics:
            summary["metrics"] = {
                "cpu_usage": metrics.get("cpu_usage", 0.0),
                "cpu_utilization_pct_of_limit": metrics.get("cpu_utilization_pct_of_limit", 0.0),
                "cpu_throttling_ratio": metrics.get("cpu_throttling_ratio", 0.0),
                "memory_usage": metrics.get("memory_usage", 0.0),
                "memory_utilization_pct_of_limit": metrics.get("memory_utilization_pct_of_limit", 0.0),
                "error_rate": metrics.get("error_rate", 0.0),
                "p95_latency_ms": metrics.get("p95_latency_ms", 0.0),
                "p99_latency_ms": metrics.get("p99_latency_ms", 0.0),
                "resource_metrics_available": metrics.get("resource_metrics_available", False),
                "application_metrics_available": metrics.get("application_metrics_available", False),
            }
            gaps = list(metrics.get("resource_metric_gaps", []) or [])
            if gaps:
                summary["resource_metric_gaps"] = gaps[:6]
            summary["metrics_signal"] = self._metrics_signal_summary(metrics)

        if "trace_count" in output:
            trace_count = int(output.get("trace_count", 0) or 0)
            if output.get("error") or bool(output.get("observability_error", False)) or str(output.get("trace_quality", "")).strip() == "unavailable":
                summary["trace_signal"] = "trace data unavailable from Jaeger"
                summary["observability_takeaway"] = (
                    "trace query failed; do not infer service failure from trace retrieval failure alone"
                )
            elif trace_count <= 0:
                summary["trace_signal"] = "no traces returned in the current lookback window"
            else:
                bottleneck = str(output.get("bottleneck_service", "")).strip()
                if bottleneck:
                    pct = float(output.get("bottleneck_pct_of_total", 0.0) or 0.0)
                    summary["trace_signal"] = f"bottleneck={bottleneck} pct={pct:.2f}"

        downstream_candidates = output.get("downstream_candidates", []) or []
        if downstream_candidates:
            summary["downstream_candidates"] = [
                {
                    "service": str(item.get("service", "")),
                    "avg_duration_ms": float(item.get("avg_duration_ms", 0.0) or 0.0),
                    "avg_pct_of_total": float(item.get("avg_pct_of_total", 0.0) or 0.0),
                    "count": int(item.get("count", 0) or 0),
                }
                for item in downstream_candidates[:3]
            ]
            top = downstream_candidates[0]
            summary["dependency_trace_signal"] = (
                f"entry={str(output.get('entry_service', 'frontend'))} "
                f"target={str(output.get('service', ''))} "
                f"downstream_bottleneck={str(top.get('service', ''))} "
                f"pct={float(top.get('avg_pct_of_total', 0.0) or 0.0):.2f}"
            )

        return summary

    def _tool_signatures(self, allowed_tools: List[str]) -> Dict[str, str]:
        signatures = {
            "get_metrics": "get_metrics(service, lookback_minutes=5) -> {call_id, timestamp, service, metrics:{cpu_usage,cpu_mcores,cpu_request_cores,cpu_limit_cores,cpu_utilization_pct_of_request,cpu_utilization_pct_of_limit,cpu_throttled_seconds_rate,cpu_throttling_ratio,memory_usage,memory_rss_bytes,memory_request_bytes,memory_limit_bytes,memory_utilization_pct_of_request,memory_utilization_pct_of_limit,error_rate,p95_latency_ms,p99_latency_ms,request_rps,error_rps,resource_metrics_available,application_metrics_available,resource_metric_gaps,application_metric_gaps}, error}",
            "get_traces": "get_traces(service, lookback_minutes=5) -> {call_id, timestamp, entry_point, call_chain, bottleneck_service, bottleneck_pct_of_total, error_spans, deviation_factor, error}",
            "get_dependency_traces": "get_dependency_traces(service, entry_service='frontend', lookback_minutes=5) -> {call_id, timestamp, service, entry_service, downstream_candidates, bottleneck_service, bottleneck_pct_of_total, trace_count, error}",
            "get_logs": "get_logs(service, tail_lines=100) -> {call_id, timestamp, pod_name, error_count, error_lines, error}",
            "get_k8s_state": "get_k8s_state(service) -> {call_id, timestamp, desired_replicas, available_replicas, pod_phases, recent_events, rollout_progressing, restart_count, error}",
            "restart_pod": "restart_pod(service, pod_name='') -> {call_id, timestamp, service, pod_name, executed, command, result, error}",
            "rollout_restart": "rollout_restart(service) -> {call_id, timestamp, service, executed, command, result, error}",
            "rollout_undo": "rollout_undo(service) -> {call_id, timestamp, service, executed, command, result, error}",
            "patch_resources": "patch_resources(service, cpu_request='', cpu_limit='', memory_request='', memory_limit='', container='server') -> {call_id, timestamp, service, executed, command, result, error}",
            "wait_and_monitor": "wait_and_monitor(seconds=30) -> {call_id, timestamp, executed, command, result, error}",
            "exec_shell": "exec_shell(command) -> {call_id, timestamp, stdout, stderr, exit_code, rejected, error}",
            "submit_solution": "submit_solution(root_cause, action_taken, confidence, evidence) -> {call_id, timestamp, solution_logged, evidence_valid, invalid_evidence, error}",
        }
        return {tool: signatures[tool] for tool in allowed_tools}

    def _system_prompt(self) -> str:
        return self._pure_system_prompt()

    def _pure_system_prompt(self) -> str:
        return """
You are an SRE incident response agent investigating an active incident in a Kubernetes cluster running Online Boutique, a microservices e-commerce application.

Your job is to investigate the incident using the available tools, identify the most likely root cause, and recommend the most appropriate remediation action.

You are not told what fault was injected. You must determine it from evidence.

SERVICE TOPOLOGY

Frontend (user-facing)
  -> cartservice
       -> redis-cart
  -> productcatalogservice
  -> checkoutservice
       -> cartservice
       -> productcatalogservice
       -> paymentservice
       -> currencyservice
       -> emailservice
       -> shippingservice
  -> recommendationservice
       -> productcatalogservice
  -> currencyservice

AVAILABLE TOOLS

get_k8s_state(service)
  Returns:
  - desired_replicas
  - available_replicas
  - pod_phases
  - recent_events
  - rollout_progressing
  - restart_count

get_metrics(service, lookback_minutes=5)
  Returns:
  - metrics.cpu_usage
  - metrics.cpu_mcores
  - metrics.cpu_request_cores
  - metrics.cpu_limit_cores
  - metrics.cpu_utilization_pct_of_request
  - metrics.cpu_utilization_pct_of_limit
  - metrics.cpu_throttled_seconds_rate
  - metrics.cpu_throttling_ratio
  - metrics.memory_usage
  - metrics.memory_rss_bytes
  - metrics.memory_request_bytes
  - metrics.memory_limit_bytes
  - metrics.memory_utilization_pct_of_request
  - metrics.memory_utilization_pct_of_limit
  - metrics.error_rate
  - metrics.p95_latency_ms
  - metrics.p99_latency_ms
  - metrics.request_rps
  - metrics.error_rps
  - metrics.resource_metrics_available
  - metrics.application_metrics_available
  - metrics.resource_metric_gaps
  - metrics.application_metric_gaps

get_traces(service, lookback_minutes=5)
  Returns:
  - call_chain
  - bottleneck_service
  - bottleneck_pct_of_total
  - deviation_factor
  - error_spans
  - trace_count

get_dependency_traces(service, entry_service="frontend", lookback_minutes=5)
  Returns:
  - downstream_candidates
  - bottleneck_service
  - bottleneck_pct_of_total
  - trace_count
  - entry_service
  - summary

get_logs(service, tail_lines=100)
  Returns:
  - error_count
  - error_lines
  - per-pod log_error details
  - possibly a top-level error if logs cannot be read because the container is not healthy yet

SAFE ACTION TOOLS

restart_pod(service, pod_name="")
  Deletes one pod for the service so Kubernetes recreates it

rollout_restart(service)
  Restarts a deployment safely through Kubernetes rollout controls

rollout_undo(service)
  Reverts a deployment to the previous ReplicaSet

patch_resources(service, cpu_request="", cpu_limit="", memory_request="", memory_limit="", container="server")
  Patches deployment resource requests or limits

wait_and_monitor(seconds=30)
  Records that the safest action is to observe and recheck later

submit_solution(root_cause, action_taken, confidence, evidence)
  evidence must be a list of real call_ids from the current investigation

MISSION

Investigate the current incident and determine:
1. the root cause
2. the best remediation action
3. the evidence supporting your conclusion

INVESTIGATION PRINCIPLES

1. Evidence first
- Do not assume the fault type.
- Do not name a service as the root cause unless you retrieved evidence about that service.
- Do not recommend remediation without evidence supporting it.

2. Reduce uncertainty
- At each step, choose the tool call that most reduces uncertainty.
- Prefer tools that distinguish between competing explanations.
- Avoid gathering redundant evidence if you already have enough to support a conclusion.
- Refine your hypothesis after each observation. Move from vague symptoms to a more specific likely cause.
- Before calling a tool, ask whether either possible result would materially change your diagnosis or action.
- If the next tool is unlikely to change the diagnosis or action, submit instead of continuing to gather evidence.

3. Use the right signals
- Start by inspecting Kubernetes state to understand cluster health.
- Use traces when dependency behavior, latency concentration, or request-path localization is unclear.
- Use get_dependency_traces when a service itself looks healthy but may be waiting on one of its downstream calls.
- Use metrics when resource pressure, traffic anomalies, or performance degradation is suspected.
- Use logs to confirm specific failure modes such as rollout issues, crash behavior, dependency errors, or repeated restarts.
- If get_traces returns transport or API errors, treat trace data as unavailable observability evidence. Do not infer service unhealthiness from trace retrieval failure alone.

4. Be conservative with action
- Prefer the smallest safe action that matches the evidence.
- Do not restart healthy services without justification.
- Do not choose broad actions when a more targeted action is better supported.

5. Ground all final claims
- Every claim in the final solution must be supported by real tool outputs from this run.
- Every final solution must cite real call_ids returned by prior tool calls.
- Never fabricate tool results or evidence.

IMPORTANT CONSTRAINTS

- Maximum 35 tool calls per investigation.
- You must call at least 2 tools before submitting.
- If Jaeger is enabled and the incident appears latency-related or dependency-related, use get_traces at least once before blaming a downstream dependency unless traces are unavailable or empty.
- If get_traces on a downstream service is weak or empty, prefer get_dependency_traces(service, entry_service="frontend") over guessing among dependencies.
- Do not use raw shell when a typed safe action tool can express the action.
- Do not delete deployments.
- Do not submit blank fields.
- If evidence is conflicting or incomplete, continue investigating or submit the best-supported hypothesis with appropriately lower confidence.

COMMON DIAGNOSTIC PATTERNS

Use these as guidance, not rigid rules:

- Rollout issues are often indicated by:
  - available_replicas < desired_replicas
  - rollout_progressing
  - ImagePullBackOff, ErrImagePull, CrashLoopBackOff, failed image pulls, or startup failures in events or logs

- Dependency outages are often indicated by:
  - an upstream service appearing healthy
  - a downstream service showing degraded Kubernetes state or severe errors
  - traces or logs showing failures concentrated on the downstream dependency

- Network faults are often indicated by:
  - one service-to-service hop dominating latency in traces
  - both endpoint services appearing healthy
  - metrics not strongly indicating resource exhaustion or deployment failure

- Resource exhaustion is often indicated by:
  - very high CPU or memory pressure
  - pods running but unstable or degraded
  - throttling, OOM, or repeated crash symptoms in logs or events

- Cascading failures are often indicated by:
  - multiple degraded services
  - more than one plausible fault source
  - traces, logs, or state showing separate issues that must be prioritized

STOPPING GUIDANCE

You should submit when:
- you have enough evidence to support one root cause more strongly than the alternatives
- additional tool calls are unlikely to materially change the diagnosis
- you can justify the action with specific evidence

Do not keep investigating once the diagnosis is already well-supported.
Do not stop early if major uncertainty remains.

TOOL SELECTION DISCIPLINE

- Choose the next tool because it separates your leading hypothesis from the best alternative.
- If a service is currently unavailable, logs and Kubernetes state usually reduce uncertainty more than metrics or traces on that same unavailable service.
- If a service is unavailable and you have not inspected its logs yet, logs are usually the highest-value next step on that same service.
- If a service is healthy but slow and you suspect a downstream dependency, get_dependency_traces is usually more informative than get_k8s_state on a guessed dependency.
- Avoid repeating the same tool on the same target unless you expect a time-based change that could alter the conclusion.
- State what result would change your mind before making another tool call.
- If the next tool would only confirm what you already know, submit.

FEW-SHOT EXAMPLE

Observation:
- get_k8s_state(productcatalogservice) shows desired_replicas=2, available_replicas=0, rollout_progressing=true

Good next step:
- get_logs(productcatalogservice)

Why:
- logs or startup failures distinguish rollout/startup failure from transient unavailability better than metrics or traces on the same unavailable service.

Then if logs show image pull or startup failures:
- submit_solution with the best-supported rollout failure diagnosis and the safest targeted remediation.

Stopping logic in that example:
- After unavailable deployment plus image-pull/startup failure evidence, metrics on the same service would not change the remediation decision.
- Because the next result would not materially change the diagnosis or action, submit instead of calling another tool.

IMPORTANT RESPONSE FORMAT

For every decision, populate these JSON fields:
- belief
- uncertainty
- next_evidence_needed
- leading_hypothesis
- alternative_hypothesis
- evidence_supporting_leading
- evidence_against_alternative
- what_result_would_change_my_mind
- decision_impact
- why_this_tool_reduces_uncertainty
- why_not_submit_now
- tool
- tool_input
- root_cause
- action_taken
- confidence
- evidence

If you choose submit_solution, you must also populate:
- root_cause
- action_taken
- confidence
- evidence

If you are not submitting yet:
- set root_cause to an empty string
- set action_taken to an empty string
- set confidence to 0
- set evidence to an empty list
""".strip()

    def _resolve_service(self, tool: str, tool_input: Dict[str, Any]) -> str:
        requested = str(tool_input.get("service", "")).strip()
        return requested or self._default_service()

    def _prepare_submission(self, decision: Dict[str, Any]) -> tuple[str, str, float, List[str]]:
        root_cause = str(decision.get("root_cause", "")).strip()
        action_taken = str(decision.get("action_taken", "")).strip()
        confidence = float(decision.get("confidence", 0.0) or 0.0)
        evidence = [str(item).strip() for item in list(decision.get("evidence", []) or []) if str(item).strip()]

        if confidence <= 0.0 and (root_cause or action_taken):
            confidence = 0.5

        return root_cause, action_taken, confidence, evidence

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
                return self._normalize_service_name(requested)
            return self._normalize_service_name(self._default_service())
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
                    "service": self._normalize_service_name(
                        str((step.get("inputs", {}) or {}).get("service", "")).strip()
                        or str(output.get("service", "")).strip()
                    ),
                    "summary": self._summarize_output_for_prompt(output),
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
        return self._service_unavailable(k8s_step.get("output", {}) or {})

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
        normalized = self._normalize_service_name(service)
        for step in reversed(self._evidence_steps()):
            if step.get("tool_called") != tool:
                continue
            step_service = self._normalize_service_name(
                str((step.get("inputs", {}) or {}).get("service", "")).strip()
                or str((step.get("output", {}) or {}).get("service", "")).strip()
            )
            if step_service == normalized:
                return step
        return None

    def _services_with_evidence(self) -> List[str]:
        candidates: List[str] = []
        for step in self._evidence_steps():
            service = self._normalize_service_name(
                str((step.get("inputs", {}) or {}).get("service", "")).strip()
                or str((step.get("output", {}) or {}).get("service", "")).strip()
            )
            if service and service not in candidates:
                candidates.append(service)
        for service in self._focus_services():
            normalized = self._normalize_service_name(service)
            if normalized and normalized not in candidates:
                candidates.append(normalized)
        return candidates

    def _normalize_service_name(self, service: str) -> str:
        cleaned = service.strip().lower().lstrip("/")
        if not cleaned:
            return ""
        canonical = self._canonical_service_token(cleaned)
        for known_service in SERVICE_TOPOLOGY:
            if self._canonical_service_token(known_service) == canonical:
                return known_service
        tail = cleaned.split("/")[-1].split(".")[-1]
        tail_canonical = self._canonical_service_token(tail)
        for known_service in SERVICE_TOPOLOGY:
            if self._canonical_service_token(known_service) == tail_canonical:
                return known_service
        return tail

    def _canonical_service_token(self, value: str) -> str:
        return "".join(char for char in value.lower() if char.isalnum())

    def _collect_output_text(self, output: Dict[str, Any]) -> str:
        parts: List[str] = []
        if output.get("error"):
            parts.append(str(output.get("error")))
        for key in ("error_lines",):
            for line in output.get(key, []) or []:
                parts.append(str(line))
        for event in output.get("recent_events", []) or []:
            parts.append(str((event or {}).get("reason", "")))
            parts.append(str((event or {}).get("message", "")))
        for pod in output.get("pods", []) or []:
            parts.append(str((pod or {}).get("log_error", "")))
            for line in (pod or {}).get("error_lines", []) or []:
                parts.append(str(line))
        for span in output.get("error_spans", []) or []:
            parts.append(str((span or {}).get("service", "")))
            parts.append(str((span or {}).get("error_message", "")))
        for hop in output.get("call_chain", []) or []:
            parts.append(str((hop or {}).get("error_message", "")))
            parts.append(str((hop or {}).get("operation", "")))
            parts.append(str((hop or {}).get("peer_service", "")))
        return " ".join(part for part in parts if part)

    def _extract_markers(self, text: str, markers: Tuple[str, ...]) -> List[str]:
        found: List[str] = []
        for marker in markers:
            if marker in text and marker not in found:
                found.append(marker)
        return found

    def _metrics_signal_summary(self, metrics: Dict[str, Any]) -> str:
        resource_metrics_available = bool(metrics.get("resource_metrics_available", False))
        application_metrics_available = bool(metrics.get("application_metrics_available", True))
        cpu_usage = float(metrics.get("cpu_usage", 0.0) or 0.0) if metrics.get("cpu_usage") is not None else 0.0
        cpu_pct_limit = float(metrics.get("cpu_utilization_pct_of_limit", 0.0) or 0.0) if metrics.get("cpu_utilization_pct_of_limit") is not None else 0.0
        cpu_throttling_ratio = float(metrics.get("cpu_throttling_ratio", 0.0) or 0.0) if metrics.get("cpu_throttling_ratio") is not None else 0.0
        memory_pct_limit = float(metrics.get("memory_utilization_pct_of_limit", 0.0) or 0.0) if metrics.get("memory_utilization_pct_of_limit") is not None else 0.0
        error_rate = float(metrics.get("error_rate", 0.0) or 0.0) if metrics.get("error_rate") is not None else 0.0
        latency_ms = float(metrics.get("p99_latency_ms", 0.0) or 0.0) if metrics.get("p99_latency_ms") is not None else 0.0

        if not application_metrics_available and not resource_metrics_available:
            return "metrics_unavailable"
        if not resource_metrics_available:
            error_band = "high" if error_rate >= 0.05 else "moderate" if error_rate >= 0.01 else "low"
            latency_band = "high" if latency_ms >= 1000 else "elevated" if latency_ms >= 250 else "low"
            return f"resource_metrics=missing error_rate={error_band} latency={latency_band}"

        cpu_band = "high" if cpu_pct_limit >= 80 or cpu_usage >= 0.15 else "moderate" if cpu_pct_limit >= 50 or cpu_usage >= 0.08 else "low"
        throttle_band = "high" if cpu_throttling_ratio >= 0.2 else "moderate" if cpu_throttling_ratio >= 0.05 else "low"
        memory_band = "high" if memory_pct_limit >= 85 else "moderate" if memory_pct_limit >= 65 else "low"
        error_band = "high" if error_rate >= 0.05 else "moderate" if error_rate >= 0.01 else "low"
        latency_band = "high" if latency_ms >= 1000 else "elevated" if latency_ms >= 250 else "low"
        return f"cpu={cpu_band} throttle={throttle_band} memory={memory_band} error_rate={error_band} latency={latency_band}"

    def _service_unavailable(self, output: Dict[str, Any]) -> bool:
        desired = int(output.get("desired_replicas", 0) or 0)
        available = int(output.get("available_replicas", 0) or 0)
        return desired > 0 and available < desired

    def _service_healthy(self, output: Dict[str, Any]) -> bool:
        desired = int(output.get("desired_replicas", 0) or 0)
        available = int(output.get("available_replicas", 0) or 0)
        return desired > 0 and available >= desired and not bool(output.get("rollout_progressing", False))

    def _dominant_trace_link(self, trace_output: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        dominant: Optional[Dict[str, Any]] = None
        for hop in trace_output.get("call_chain", []) or []:
            caller = self._normalize_service_name(str((hop or {}).get("service", "")))
            callee = self._normalize_service_name(str((hop or {}).get("peer_service", "")))
            if not caller or not callee or caller == callee:
                continue
            pct = float((hop or {}).get("pct_of_total", 0.0) or 0.0)
            candidate = {
                "caller": caller,
                "callee": callee,
                "pct_of_total": pct,
                "duration_ms": float((hop or {}).get("duration_ms", 0.0) or 0.0),
                "error": bool((hop or {}).get("error", False)),
                "error_message": str((hop or {}).get("error_message", "")),
            }
            if dominant is None or candidate["pct_of_total"] > dominant["pct_of_total"]:
                dominant = candidate
        return dominant

    def _diagnostic_tokens(self, step: Dict[str, Any]) -> set[str]:
        tool = str(step.get("tool_called", "")).strip()
        output = step.get("output", {}) or {}
        service = self._normalize_service_name(
            str((step.get("inputs", {}) or {}).get("service", "")).strip()
            or str(output.get("service", "")).strip()
        )
        tokens: set[str] = set()
        if service:
            tokens.add(f"service:{service}")

        text = self._collect_output_text(output).lower()
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
            bottleneck = self._normalize_service_name(str(output.get("bottleneck_service", "")))
            if bottleneck:
                tokens.add(f"bottleneck:{bottleneck}")
            dominant = self._dominant_trace_link(output)
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

    def _truncate(self, value: str, limit: int) -> str:
        if len(value) <= limit:
            return value
        return value[: max(0, limit - 3)] + "..."

    def _rate_limit(self) -> None:
        if self._last_llm_call_at is None:
            return
        sleep_seconds = RATE_LIMIT_SECONDS.get(self.provider, 0)
        if sleep_seconds <= 0:
            return
        elapsed = time.time() - self._last_llm_call_at
        if elapsed < sleep_seconds:
            time.sleep(sleep_seconds - elapsed)

    def _normalize_provider(self, provider: str) -> str:
        normalized = provider.strip().lower()
        if normalized == "claude":
            return "anthropic"
        return normalized

    def _default_model(self, provider: str) -> str:
        if provider == "ollama":
            return os.environ.get("OLLAMA_MODEL", DEFAULT_MODELS["ollama"])
        if provider == "gemini":
            return os.environ.get("GEMINI_MODEL", DEFAULT_MODELS["gemini"])
        if provider == "openai":
            return os.environ.get("OPENAI_MODEL", DEFAULT_MODELS["openai"])
        if provider == "anthropic":
            return os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODELS["anthropic"])
        return DEFAULT_MODELS.get(provider, DEFAULT_MODELS["openai"])
