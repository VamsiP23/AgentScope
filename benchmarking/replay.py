from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4


@dataclass
class ReplayDataset:
    path: Path
    metadata: Dict[str, Any]
    initial_context: Dict[str, Any]
    calls: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "ReplayDataset":
        payload = json.loads(path.read_text())
        initial_context = payload.get("initial_context", {}) or {}
        if isinstance(initial_context, str):
            initial_context = {
                "summary": initial_context,
                "suspicious_services": [str(payload.get("fault_spec", {}).get("target_service", "")).strip()],
            }
        elif not isinstance(initial_context, dict):
            initial_context = {"summary": str(initial_context)}

        metadata = dict(payload.get("metadata", {}) or {})
        if not metadata:
            provenance = dict(payload.get("provenance", {}) or {})
            metadata = {
                "task_id": str(payload.get("task_id", "")),
                "family": str(payload.get("family", "")),
                "namespace": str(provenance.get("namespace", "default") or "default"),
                "captured_at_utc": str(provenance.get("capture_timestamp_utc", "")),
            }

        calls = list(payload.get("calls", []) or [])
        if not calls and payload.get("phases"):
            calls = _calls_from_episode_phases(list(payload.get("phases", []) or []))

        return cls(
            path=path.resolve(),
            metadata=metadata,
            initial_context=dict(initial_context),
            calls=calls,
        )


def _calls_from_episode_phases(phases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []
    for phase in phases:
        responses = dict((phase or {}).get("tool_responses", {}) or {})
        for fingerprint, output in responses.items():
            method, inputs = _parse_episode_fingerprint(str(fingerprint))
            if not method:
                continue
            calls.append(
                {
                    "method": method,
                    "inputs": inputs,
                    "outputs": dict(output or {}),
                }
            )
    return calls


def _parse_episode_fingerprint(fingerprint: str) -> Tuple[str, Dict[str, Any]]:
    parts = [part.strip() for part in fingerprint.split("|") if part.strip()]
    if not parts:
        return "", {}
    method = parts[0]
    inputs: Dict[str, Any] = {}
    for part in parts[1:]:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        inputs[key.strip()] = value.strip()
    return method, inputs


class ReplayAgentCloudInterface:
    def __init__(self, dataset_path: str, run_log_path: str = "") -> None:
        self.dataset = ReplayDataset.load(Path(dataset_path))
        self.run_id = str(uuid4())
        self.run_log_path = Path(run_log_path) if run_log_path else Path("results") / "aci" / f"{self.run_id}.jsonl"
        self.run_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.run_log: List[Dict[str, Any]] = []
        self.submitted_solution: Optional[Dict[str, Any]] = None
        self.jaeger_enabled = True
        self.namespace = str(self.dataset.metadata.get("namespace", "default"))
        self.prom_url = "replay://prometheus"
        self.jaeger_url = "replay://jaeger"
        self._remaining_calls = list(self.dataset.calls)

    def get_metrics(self, service: str, lookback_minutes: int = 5) -> Dict[str, Any]:
        return self._recorded_call("get_metrics", {"service": service, "lookback_minutes": lookback_minutes})

    def get_traces(self, service: str, lookback_minutes: int = 5) -> Dict[str, Any]:
        return self._recorded_call("get_traces", {"service": service, "lookback_minutes": lookback_minutes})

    def get_dependency_traces(
        self,
        service: str,
        entry_service: str = "frontend",
        lookback_minutes: int = 5,
    ) -> Dict[str, Any]:
        return self._recorded_call(
            "get_dependency_traces",
            {"service": service, "entry_service": entry_service, "lookback_minutes": lookback_minutes},
        )

    def get_logs(self, service: str, tail_lines: int = 100) -> Dict[str, Any]:
        return self._recorded_call("get_logs", {"service": service, "tail_lines": tail_lines})

    def get_k8s_state(self, service: str) -> Dict[str, Any]:
        return self._recorded_call("get_k8s_state", {"service": service})

    def get_trace_by_id(self, trace_id: str) -> Dict[str, Any]:
        return self._recorded_call("get_trace_by_id", {"trace_id": trace_id})

    def restart_pod(self, service: str, pod_name: str = "") -> Dict[str, Any]:
        return self._simulated_action("restart_pod", {"service": service, "pod_name": pod_name})

    def rollout_restart(self, service: str) -> Dict[str, Any]:
        return self._simulated_action("rollout_restart", {"service": service})

    def rollout_undo(self, service: str) -> Dict[str, Any]:
        return self._simulated_action("rollout_undo", {"service": service})

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
        return self._simulated_action(
            "patch_resources",
            {
                "service": service,
                "cpu_request": cpu_request,
                "cpu_limit": cpu_limit,
                "memory_request": memory_request,
                "memory_limit": memory_limit,
                "container": container,
            },
        )

    def wait_and_monitor(self, seconds: int = 30) -> Dict[str, Any]:
        return self._simulated_action("wait_and_monitor", {"seconds": seconds})

    def exec_shell(self, command: str) -> Dict[str, Any]:
        return self._simulated_action("exec_shell", {"command": command}, executed=False, rejected=True)

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
        payload = {
            "call_id": str(uuid4()),
            "timestamp": self._timestamp(),
            "solution_logged": True,
            "evidence_valid": True,
            "invalid_evidence": [],
            "root_cause": root_cause,
            "action_taken": action_taken,
            "fault_class": fault_class,
            "affected_service": affected_service,
            "action_type": action_type,
            "confidence": confidence,
            "evidence": list(evidence),
            "error": None,
        }
        self.submitted_solution = dict(payload)
        self._append_log("submit_solution", {
            "root_cause": root_cause,
            "action_taken": action_taken,
            "fault_class": fault_class,
            "affected_service": affected_service,
            "action_type": action_type,
            "confidence": confidence,
            "evidence": list(evidence),
        }, payload)
        return payload

    def _recorded_call(self, method: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        idx, record = self._find_match(method, inputs)
        if record is None:
            output = {
                "error": f"no replay record found for {method} with inputs {inputs}",
                "call_id": str(uuid4()),
                "timestamp": self._timestamp(),
            }
            self._append_log(method, inputs, output)
            return output
        self._remaining_calls.pop(idx)
        output = dict(record.get("outputs", {}) or {})
        output.setdefault("call_id", str(uuid4()))
        output.setdefault("timestamp", self._timestamp())
        self._append_log(method, inputs, output)
        return output

    def _simulated_action(
        self,
        method: str,
        inputs: Dict[str, Any],
        *,
        executed: bool = True,
        rejected: bool = False,
    ) -> Dict[str, Any]:
        output = {
            "call_id": str(uuid4()),
            "timestamp": self._timestamp(),
            "executed": executed,
            "replay_mode": True,
            "rejected": rejected,
            "command": "",
            "result": f"simulated {method}",
            "error": None if executed else "replay backend does not execute shell actions",
        }
        self._append_log(method, inputs, output)
        return output

    def _find_match(self, method: str, inputs: Dict[str, Any]) -> Tuple[int, Optional[Dict[str, Any]]]:
        exact: Tuple[int, Optional[Dict[str, Any]]] = (-1, None)
        fallback: Tuple[int, Optional[Dict[str, Any]]] = (-1, None)
        for idx, record in enumerate(self._remaining_calls):
            if str(record.get("method", "")).strip() != method:
                continue
            recorded_inputs = dict(record.get("inputs", {}) or {})
            normalized_recorded = self._normalized_inputs(method, recorded_inputs)
            normalized_requested = self._normalized_inputs(method, inputs)
            if normalized_recorded == normalized_requested:
                exact = (idx, record)
                break
            if self._same_target(method, normalized_recorded, normalized_requested) and fallback[1] is None:
                fallback = (idx, record)
        return exact if exact[1] is not None else fallback

    def _normalized_inputs(self, method: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(inputs)
        if method in {"get_metrics", "get_traces"}:
            normalized["lookback_minutes"] = int(inputs.get("lookback_minutes", 5) or 5)
        elif method == "get_dependency_traces":
            normalized["lookback_minutes"] = int(inputs.get("lookback_minutes", 5) or 5)
            normalized["entry_service"] = str(inputs.get("entry_service", "frontend")).strip() or "frontend"
        elif method == "get_logs":
            normalized["tail_lines"] = int(inputs.get("tail_lines", 100) or 100)
        return normalized

    def _same_target(self, method: str, recorded: Dict[str, Any], requested: Dict[str, Any]) -> bool:
        if method in {"get_metrics", "get_traces", "get_k8s_state", "get_logs"}:
            return str(recorded.get("service", "")).strip() == str(requested.get("service", "")).strip()
        if method == "get_dependency_traces":
            return (
                str(recorded.get("service", "")).strip() == str(requested.get("service", "")).strip()
                and str(recorded.get("entry_service", "")).strip() == str(requested.get("entry_service", "")).strip()
            )
        if method == "get_trace_by_id":
            return str(recorded.get("trace_id", "")).strip() == str(requested.get("trace_id", "")).strip()
        return False

    def _append_log(self, method: str, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        record = {
            "method": method,
            "inputs": dict(inputs),
            "outputs": dict(outputs),
        }
        self.run_log.append(record)
        with self.run_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

    def _timestamp(self) -> str:
        return str(self.dataset.metadata.get("captured_at_utc", ""))
