from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from agent_graph.aci_support import (
    action_output,
    append_jsonl_record,
    build_call_record,
    dependency_trace_output,
    metrics_output,
    trace_detail_output,
    trace_summary_output,
    utc_timestamp,
    validate_solution_payload,
)
from agent_graph.evidence_distiller import EVIDENCE_TOOLS, EvidenceDistiller
from agent_graph.tools.actions import ActionTools
from agent_graph.tools.jaeger import JaegerTools
from agent_graph.tools.kubernetes import KubernetesTools
from agent_graph.tools.prometheus import PrometheusTools


class AgentCloudInterface:
    def __init__(
        self,
        namespace: str = "default",
        prom_url: str = "http://localhost:9090",
        jaeger_url: str = "http://localhost:16686",
        kubectl_context: str = "",
        run_id: str = "",
        run_log_path: str = "",
        jaeger_enabled: bool = True,
        dry_run: bool = True,
        evidence_view: str = "",
    ) -> None:
        self.namespace = namespace
        self.prom_url = prom_url
        self.jaeger_url = jaeger_url
        self.kubectl_context = kubectl_context.strip()
        self.jaeger_enabled = jaeger_enabled
        self.dry_run = dry_run
        self.evidence_view = (evidence_view or os.environ.get("AGENTSCOPE_EVIDENCE_VIEW", "raw")).strip().lower()
        if self.evidence_view not in {"raw", "compact", "distilled"}:
            raise ValueError(f"unsupported evidence_view: {self.evidence_view}")
        self.distiller = EvidenceDistiller()

        self.run_id = run_id or str(uuid4())
        default_log_path = Path("results") / "aci" / f"{self.run_id}.jsonl"
        self.run_log_path = Path(run_log_path) if run_log_path else default_log_path
        self.run_log_path.parent.mkdir(parents=True, exist_ok=True)

        self.prom = PrometheusTools(prom_url)
        self.k8s = KubernetesTools(kubectl_context=self.kubectl_context)
        self.jaeger = JaegerTools(jaeger_url)
        self.actions = ActionTools()

        self.run_log: List[Dict[str, Any]] = []
        self.submitted_solution: Optional[Dict[str, Any]] = None

    def reset_trace_cache(self) -> None:
        """Compatibility hook for evidence collectors that retry Jaeger probes."""
        reset = getattr(self.jaeger, "reset_cache", None)
        if callable(reset):
            reset()

    def get_metrics(self, service: str, lookback_minutes: int = 5) -> Dict[str, Any]:
        return self._run_logged_call(
            "get_metrics",
            {"service": service, "lookback_minutes": lookback_minutes},
            lambda: self._get_metrics_impl(service, lookback_minutes),
        )

    def get_traces(self, service: str, lookback_minutes: int = 5) -> Dict[str, Any]:
        return self._run_logged_call(
            "get_traces",
            {"service": service, "lookback_minutes": lookback_minutes},
            lambda: self._get_traces_impl(service, lookback_minutes),
        )

    def get_dependency_traces(
        self,
        service: str,
        entry_service: str = "frontend",
        lookback_minutes: int = 5,
    ) -> Dict[str, Any]:
        return self._run_logged_call(
            "get_dependency_traces",
            {
                "service": service,
                "entry_service": entry_service,
                "lookback_minutes": lookback_minutes,
            },
            lambda: self._get_dependency_traces_impl(service, entry_service, lookback_minutes),
        )

    def get_logs(self, service: str, tail_lines: int = 100) -> Dict[str, Any]:
        return self._run_logged_call(
            "get_logs",
            {"service": service, "tail_lines": tail_lines},
            lambda: self.k8s.service_logs(
                self.namespace,
                service,
                tail_lines=tail_lines,
                kubectl_context=self.kubectl_context,
            ),
        )

    def get_trace_by_id(self, trace_id: str) -> Dict[str, Any]:
        return self._run_logged_call(
            "get_trace_by_id",
            {"trace_id": trace_id},
            lambda: self._get_trace_by_id_impl(trace_id),
        )

    def get_k8s_state(self, service: str) -> Dict[str, Any]:
        return self._run_logged_call(
            "get_k8s_state",
            {"service": service},
            lambda: self.k8s.service_state(
                self.namespace,
                service,
                limit=10,
                kubectl_context=self.kubectl_context,
            ),
        )

    def exec_shell(self, command: str) -> Dict[str, Any]:
        return self._run_logged_call(
            "exec_shell",
            {"command": command},
            lambda: self.k8s.exec_shell(command, kubectl_context=self.kubectl_context),
        )

    def restart_pod(self, service: str, pod_name: str = "") -> Dict[str, Any]:
        return self._run_logged_call(
            "restart_pod",
            {"service": service, "pod_name": pod_name},
            lambda: self._restart_pod_impl(service, pod_name),
        )

    def rollout_restart(self, service: str) -> Dict[str, Any]:
        return self._run_logged_call(
            "rollout_restart",
            {"service": service},
            lambda: self._action_result(
                service,
                self.actions.rollout_restart(self.namespace, service, dry_run=self.dry_run),
            ),
        )

    def rollout_undo(self, service: str) -> Dict[str, Any]:
        return self._run_logged_call(
            "rollout_undo",
            {"service": service},
            lambda: self._action_result(
                service,
                self.actions.rollout_undo(self.namespace, service, dry_run=self.dry_run),
            ),
        )

    def patch_resources(
        self,
        service: str,
        *,
        cpu_request: str = "",
        cpu_limit: str = "",
        memory_request: str = "",
        memory_limit: str = "",
        container: str = "server",
    ) -> Dict[str, Any]:
        return self._run_logged_call(
            "patch_resources",
            {
                "service": service,
                "cpu_request": cpu_request,
                "cpu_limit": cpu_limit,
                "memory_request": memory_request,
                "memory_limit": memory_limit,
                "container": container,
            },
            lambda: self._action_result(
                service,
                self.actions.patch_resources(
                    self.namespace,
                    service,
                    container=container,
                    cpu_request=cpu_request,
                    cpu_limit=cpu_limit,
                    memory_request=memory_request,
                    memory_limit=memory_limit,
                    dry_run=self.dry_run,
                ),
            ),
        )

    def wait_and_monitor(self, seconds: int = 30) -> Dict[str, Any]:
        return self._run_logged_call(
            "wait_and_monitor",
            {"seconds": seconds},
            lambda: self._action_result(
                "",
                self.actions.wait_and_monitor(seconds),
            ),
        )

    def submit_solution(
        self,
        root_cause: str,
        action_taken: str,
        confidence: float,
        evidence: List[str],
        fault_class: str = "",
        affected_service: str = "",
        action_type: str = "",
    ) -> Dict[str, Any]:
        return self._run_logged_call(
            "submit_solution",
            {
                "root_cause": root_cause,
                "action_taken": action_taken,
                "fault_class": fault_class,
                "affected_service": affected_service,
                "action_type": action_type,
                "confidence": confidence,
                "evidence": list(evidence),
            },
            lambda: self._submit_solution_impl(
                root_cause,
                action_taken,
                confidence,
                evidence,
                fault_class=fault_class,
                affected_service=affected_service,
                action_type=action_type,
            ),
        )

    def _get_metrics_impl(self, service: str, lookback_minutes: int) -> Dict[str, Any]:
        metrics = self.prom.service_metrics(self.namespace, service, lookback_minutes=lookback_minutes)
        return metrics_output(service, metrics)

    def _get_traces_impl(self, service: str, lookback_minutes: int) -> Dict[str, Any]:
        if not self.jaeger_enabled:
            return {"error": "jaeger disabled"}

        summary = self.jaeger.get_service_trace_summary(service, lookback_minutes=lookback_minutes, limit=20)
        return trace_summary_output(service, summary)

    def _get_dependency_traces_impl(self, service: str, entry_service: str, lookback_minutes: int) -> Dict[str, Any]:
        if not self.jaeger_enabled:
            return {"error": "jaeger disabled"}

        summary = self.jaeger.get_dependency_trace_summary(
            service,
            entry_service=entry_service,
            lookback_minutes=lookback_minutes,
            limit=20,
        )
        return dependency_trace_output(service, entry_service, summary)

    def _submit_solution_impl(
        self,
        root_cause: str,
        action_taken: str,
        confidence: float,
        evidence: List[str],
        fault_class: str = "",
        affected_service: str = "",
        action_type: str = "",
    ) -> Dict[str, Any]:
        solution = validate_solution_payload(
            self.run_log,
            root_cause,
            action_taken,
            confidence,
            evidence,
            fault_class=fault_class,
            affected_service=affected_service,
            action_type=action_type,
        )
        self.submitted_solution = solution
        return solution

    def _restart_pod_impl(self, service: str, pod_name: str) -> Dict[str, Any]:
        pod = pod_name.strip()
        if not pod:
            pods = self.k8s.pods_for_service(self.namespace, service, kubectl_context=self.kubectl_context)
            if not pods:
                return {
                    "service": service,
                    "pod_name": "",
                    "executed": False,
                    "command": [],
                    "result": {},
                    "error": f"no pods found for service {service}",
                }
            pod = pods[0]
        return self._action_result(
            service,
            self.actions.restart_pod(self.namespace, pod, dry_run=self.dry_run),
            pod_name=pod,
        )

    def _action_result(self, service: str, result: Dict[str, Any], *, pod_name: str = "") -> Dict[str, Any]:
        return action_output(service, self.dry_run, result, pod_name=pod_name)

    def _get_trace_by_id_impl(self, trace_id: str) -> Dict[str, Any]:
        if not self.jaeger_enabled:
            return {"error": "jaeger disabled"}
        detail = self.jaeger.get_trace_detail(trace_id)
        return trace_detail_output(trace_id, detail)

    def _run_logged_call(
        self,
        method: str,
        inputs: Dict[str, Any],
        fn: Callable[[], Dict[str, Any]],
    ) -> Dict[str, Any]:
        call_id = str(uuid4())
        timestamp = utc_timestamp()

        try:
            output = fn()
            if not isinstance(output, dict):
                output = {"result": output}
        except Exception as exc:
            output = {"error": str(exc)}

        output.setdefault("error", None)
        output["call_id"] = call_id
        output["timestamp"] = timestamp
        if self.evidence_view in {"compact", "distilled"} and method in EVIDENCE_TOOLS:
            output = self.distiller.distill(method, output)

        record = build_call_record(method, inputs, output)
        self.run_log.append(record)
        self._append_log(record)
        return output

    def _append_log(self, record: Dict[str, Any]) -> None:
        append_jsonl_record(self.run_log_path, record)


ACI = AgentCloudInterface
