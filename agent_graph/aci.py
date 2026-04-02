from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from agent_graph.tools.actions import ActionTools
from agent_graph.tools.jaeger import JaegerTools
from agent_graph.tools.kubernetes import KubernetesTools
from agent_graph.tools.prometheus import PrometheusTools


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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
    ) -> None:
        self.namespace = namespace
        self.prom_url = prom_url
        self.jaeger_url = jaeger_url
        self.kubectl_context = kubectl_context.strip()
        self.jaeger_enabled = jaeger_enabled
        self.dry_run = dry_run

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
    ) -> Dict[str, Any]:
        return self._run_logged_call(
            "submit_solution",
            {
                "root_cause": root_cause,
                "action_taken": action_taken,
                "confidence": confidence,
                "evidence": list(evidence),
            },
            lambda: self._submit_solution_impl(root_cause, action_taken, confidence, evidence),
        )

    def _get_metrics_impl(self, service: str, lookback_minutes: int) -> Dict[str, Any]:
        metrics = self.prom.service_metrics(self.namespace, service, lookback_minutes=lookback_minutes)
        return {
            "service": service,
            "metrics": {
                "cpu_usage": metrics.get("cpu_cores", 0.0),
                "cpu_mcores": metrics.get("cpu_mcores", 0.0),
                "cpu_request_cores": metrics.get("cpu_request_cores", 0.0),
                "cpu_limit_cores": metrics.get("cpu_limit_cores", 0.0),
                "cpu_utilization_pct_of_request": metrics.get("cpu_utilization_pct_of_request", 0.0),
                "cpu_utilization_pct_of_limit": metrics.get("cpu_utilization_pct_of_limit", 0.0),
                "cpu_headroom_cores_to_limit": metrics.get("cpu_headroom_cores_to_limit", 0.0),
                "cpu_throttled_seconds_rate": metrics.get("cpu_throttled_seconds_rate", 0.0),
                "cpu_throttled_periods_rate": metrics.get("cpu_throttled_periods_rate", 0.0),
                "cpu_periods_rate": metrics.get("cpu_periods_rate", 0.0),
                "cpu_throttling_ratio": metrics.get("cpu_throttling_ratio", 0.0),
                "memory_usage": metrics.get("memory_bytes", 0.0),
                "memory_rss_bytes": metrics.get("memory_rss_bytes", 0.0),
                "error_rate": metrics.get("error_rate", 0.0),
                "p95_latency_ms": metrics.get("latency_p95_ms", 0.0),
                "p99_latency_ms": metrics.get("latency_p99_ms", 0.0),
                "request_rps": metrics.get("request_rps", 0.0),
                "error_rps": metrics.get("error_rps", 0.0),
                "memory_mib": metrics.get("memory_mib", 0.0),
                "memory_rss_mib": metrics.get("memory_rss_mib", 0.0),
                "memory_request_bytes": metrics.get("memory_request_bytes", 0.0),
                "memory_limit_bytes": metrics.get("memory_limit_bytes", 0.0),
                "memory_request_mib": metrics.get("memory_request_mib", 0.0),
                "memory_limit_mib": metrics.get("memory_limit_mib", 0.0),
                "memory_utilization_pct_of_request": metrics.get("memory_utilization_pct_of_request", 0.0),
                "memory_utilization_pct_of_limit": metrics.get("memory_utilization_pct_of_limit", 0.0),
                "memory_headroom_bytes_to_limit": metrics.get("memory_headroom_bytes_to_limit", 0.0),
                "resource_metrics_available": metrics.get("resource_metrics_available", False),
                "application_metrics_available": metrics.get("application_metrics_available", False),
                "resource_metric_gaps": metrics.get("resource_metric_gaps", []) or [],
                "application_metric_gaps": metrics.get("application_metric_gaps", []) or [],
            },
            "error": metrics.get("error"),
        }

    def _get_traces_impl(self, service: str, lookback_minutes: int) -> Dict[str, Any]:
        if not self.jaeger_enabled:
            return {"error": "jaeger disabled"}

        summary = self.jaeger.get_service_trace_summary(service, lookback_minutes=lookback_minutes, limit=20)
        return {
            "service": service,
            "entry_point": summary.get("entry_point", service),
            "trace_count": summary.get("trace_count", 0),
            "call_chain": summary.get("call_chain", []) or [],
            "bottleneck_service": summary.get("bottleneck_service", ""),
            "bottleneck_pct_of_total": summary.get("bottleneck_pct_of_total", 0.0),
            "error_spans": summary.get("error_spans", []) or [],
            "deviation_factor": summary.get("deviation_factor", 0.0),
            "baseline_p99_ms": summary.get("baseline_p99_ms", 0.0),
            "slowest_trace_id": summary.get("slowest_trace_id", ""),
            "trace_quality": summary.get("trace_quality", "missing"),
            "observability_error": bool(summary.get("observability_error", False)),
            "observability_status": str(summary.get("observability_status", "")),
            "error": summary.get("error"),
        }

    def _get_dependency_traces_impl(self, service: str, entry_service: str, lookback_minutes: int) -> Dict[str, Any]:
        if not self.jaeger_enabled:
            return {"error": "jaeger disabled"}

        summary = self.jaeger.get_dependency_trace_summary(
            service,
            entry_service=entry_service,
            lookback_minutes=lookback_minutes,
            limit=20,
        )
        return {
            "service": service,
            "entry_service": summary.get("entry_service", entry_service),
            "trace_count": summary.get("trace_count", 0),
            "focus_trace_count": summary.get("focus_trace_count", 0),
            "raw_trace_count": summary.get("raw_trace_count", 0),
            "application_trace_count": summary.get("application_trace_count", 0),
            "call_chain": summary.get("call_chain", []) or [],
            "downstream_candidates": summary.get("downstream_candidates", []) or [],
            "bottleneck_service": summary.get("bottleneck_service", ""),
            "bottleneck_pct_of_total": summary.get("bottleneck_pct_of_total", 0.0),
            "error_spans": summary.get("error_spans", []) or [],
            "trace_quality": summary.get("trace_quality", "missing"),
            "observability_error": bool(summary.get("observability_error", False)),
            "observability_status": str(summary.get("observability_status", "")),
            "summary": str(summary.get("summary", "")),
            "error": summary.get("error"),
        }

    def _submit_solution_impl(
        self,
        root_cause: str,
        action_taken: str,
        confidence: float,
        evidence: List[str],
    ) -> Dict[str, Any]:
        root_cause = str(root_cause).strip()
        action_taken = str(action_taken).strip()
        valid_call_ids = {
            record["call_id"]
            for record in self.run_log
            if record.get("method") != "submit_solution"
        }
        invalid_evidence = [call_id for call_id in evidence if call_id not in valid_call_ids]
        validation_errors: List[str] = []
        if not root_cause:
            validation_errors.append("root_cause is required")
        if not action_taken:
            validation_errors.append("action_taken is required")
        if not evidence:
            validation_errors.append("at least one evidence call_id is required")
        if invalid_evidence:
            validation_errors.append("solution cited non-existent tool call IDs")
        solution = {
            "solution_logged": len(validation_errors) == 0,
            "root_cause": root_cause,
            "action_taken": action_taken,
            "confidence": float(confidence),
            "evidence": list(evidence),
            "evidence_valid": len(invalid_evidence) == 0,
            "invalid_evidence": invalid_evidence,
            "error": None if not validation_errors else "; ".join(validation_errors),
        }
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
        output = {
            "service": service,
            "pod_name": pod_name,
            "dry_run": self.dry_run,
            "executed": bool(result.get("executed", False)),
            "command": result.get("command", []),
            "result": result.get("result"),
            "error": None,
        }
        raw_result = result.get("result")
        if isinstance(raw_result, dict):
            stderr = str(raw_result.get("stderr", "") or "")
            stdout = str(raw_result.get("stdout", "") or "")
            returncode = int(raw_result.get("returncode", 0) or 0)
            output["exit_code"] = returncode
            output["stdout"] = stdout
            output["stderr"] = stderr
            if returncode != 0:
                output["error"] = stderr or stdout or "action failed"
        return output

    def _get_trace_by_id_impl(self, trace_id: str) -> Dict[str, Any]:
        if not self.jaeger_enabled:
            return {"error": "jaeger disabled"}
        detail = self.jaeger.get_trace_detail(trace_id)
        return {
            "trace_id": trace_id,
            "service": detail.get("service", ""),
            "total_duration_ms": detail.get("total_duration_ms", 0.0),
            "has_error": detail.get("has_error", False),
            "error_types": detail.get("error_types", []) or [],
            "hops": detail.get("hops", []) or [],
            "error": detail.get("error"),
        }

    def _run_logged_call(
        self,
        method: str,
        inputs: Dict[str, Any],
        fn: Callable[[], Dict[str, Any]],
    ) -> Dict[str, Any]:
        call_id = str(uuid4())
        timestamp = _utc_timestamp()

        try:
            output = fn()
            if not isinstance(output, dict):
                output = {"result": output}
        except Exception as exc:
            output = {"error": str(exc)}

        output.setdefault("error", None)
        output["call_id"] = call_id
        output["timestamp"] = timestamp

        record = {
            "call_id": call_id,
            "timestamp": timestamp,
            "method": method,
            "inputs": inputs,
            "outputs": output,
        }
        self.run_log.append(record)
        self._append_log(record)
        return output

    def _append_log(self, record: Dict[str, Any]) -> None:
        with self.run_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")


ACI = AgentCloudInterface
