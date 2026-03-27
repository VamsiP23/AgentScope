from __future__ import annotations

import time
from typing import Any, Dict, List

from agent_graph.reasoning.llm import ResponsesJSONClient
from agent_graph.schemas import ActionPlan, VerificationResult
from agent_graph.tools.jaeger import JaegerTools
from agent_graph.tools.kubernetes import KubernetesTools
from agent_graph.tools.prometheus import PrometheusTools
from detectors.monitor import build_report
from detectors.schemas import DetectionConfig


class Verifier:
    def __init__(self, config: DetectionConfig, jaeger_url: str, mode: str = "heuristic", wait_seconds: int = 60, poll_interval_seconds: int = 10) -> None:
        self.config = config
        self.wait_seconds = wait_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.mode = mode
        self.k8s = KubernetesTools()
        self.prom = PrometheusTools(config.prom_url)
        self.jaeger = JaegerTools(jaeger_url)
        self.llm = ResponsesJSONClient()

    def _extract_metric(self, report: Dict[str, Any], finding_name: str) -> float:
        for finding in report.get("findings", []) or []:
            if finding.get("name") == finding_name:
                try:
                    return float(finding.get("value", 0.0))
                except Exception:
                    return 0.0
        return 0.0

    def _sample(self, action: ActionPlan) -> Dict[str, Any]:
        report = build_report(self.config).to_dict()
        deployment = self.k8s.deployment_health(self.config.namespace, action.target)
        pod_status = self.k8s.deployment_pod_status(self.config.namespace, action.target)
        top_errors = self.prom.top_error_services(self.config.window, limit=5)
        service_rps = self.prom.service_rps(self.config.window, limit=10)
        trace_summary = self.jaeger.failing_downstream_summary(action.target, limit=5, lookback="1h")
        return {
            "report": report,
            "deployment": deployment,
            "pod_status": pod_status,
            "top_error_services": top_errors,
            "service_rps": service_rps,
            "trace_summary": trace_summary,
            "error_ratio": self._extract_metric(report, "error_ratio"),
            "service_error_rps": self._extract_metric(report, "service_error_rate"),
            "summary": report.get("summary", ""),
        }

    def _collect_evidence(self, action: ActionPlan, detection_before: dict) -> Dict[str, Any]:
        initial_incident = bool(detection_before.get("incident_detected", False))
        total_wait = max(0, self.wait_seconds)
        poll = max(1, self.poll_interval_seconds)
        sample_count = max(1, (total_wait // poll) + 1 if total_wait > 0 else 1)

        samples: List[Dict[str, Any]] = []
        for index in range(sample_count):
            if index > 0:
                time.sleep(poll)
            samples.append(self._sample(action))

        latest = samples[-1]
        return {
            "before": {
                "incident_detected": initial_incident,
                "summary": detection_before.get("summary", ""),
                "error_ratio": self._extract_metric(detection_before, "error_ratio"),
                "service_error_rps": self._extract_metric(detection_before, "service_error_rate"),
            },
            "after": {
                "incident_detected": latest["report"].get("incident_detected", False),
                "summary": latest["summary"],
                "error_ratio": latest["error_ratio"],
                "service_error_rps": latest["service_error_rps"],
                "deployment": latest["deployment"],
                "pod_status": latest["pod_status"],
                "top_error_services": latest["top_error_services"],
                "service_rps": latest["service_rps"],
                "trace_summary": latest["trace_summary"],
            },
            "samples": [
                {
                    "summary": sample["summary"],
                    "desired": sample["deployment"].get("desired", 0),
                    "available": sample["deployment"].get("available", 0),
                    "pod_count": sample["pod_status"].get("pod_count", 0),
                    "ready_pod_count": sample["pod_status"].get("ready_pod_count", 0),
                    "error_ratio": sample["error_ratio"],
                    "service_error_rps": sample["service_error_rps"],
                }
                for sample in samples
            ],
            "note": (
                f"verification polled every {poll}s for {total_wait}s"
                if total_wait > 0
                else "verification used immediate recheck"
            ),
        }

    def run(self, action: ActionPlan, detection_before: dict) -> VerificationResult:
        evidence = self._collect_evidence(action, detection_before)
        if self.mode == "llm":
            if not self.llm.available():
                raise RuntimeError("LLM mode requested but OPENAI_API_KEY is not set")
            try:
                return self._run_llm(action, evidence)
            except Exception as exc:
                raise RuntimeError(f"LLM verifier failed: {exc}") from exc
        return self._run_heuristic(evidence)

    def _run_heuristic(self, evidence: Dict[str, Any]) -> VerificationResult:
        before = evidence["before"]
        after = evidence["after"]
        deployment = after["deployment"]
        pod_status = after["pod_status"]
        errors_declining = (
            after["error_ratio"] <= before["error_ratio"]
            and after["service_error_rps"] <= before["service_error_rps"]
        )
        recovered = bool(before["incident_detected"]) and not bool(after["incident_detected"])
        root_cause_mitigated = bool(deployment.get("healthy", False)) and errors_declining
        return VerificationResult(
            recovered=recovered,
            root_cause_mitigated=root_cause_mitigated,
            before_incident_detected=bool(before["incident_detected"]),
            after_incident_detected=bool(after["incident_detected"]),
            before_summary=str(before["summary"]),
            after_summary=str(after["summary"]),
            note=str(evidence["note"]),
            stages={
                "final_desired": deployment.get("desired", 0),
                "final_available": deployment.get("available", 0),
                "final_pod_count": pod_status.get("pod_count", 0),
                "final_ready_pod_count": pod_status.get("ready_pod_count", 0),
                "errors_declining": errors_declining,
            },
            samples=list(evidence["samples"]),
            evidence=evidence,
        )

    def _run_llm(self, action: ActionPlan, evidence: Dict[str, Any]) -> VerificationResult:
        prompt = {
            "task": "Interpret recovery evidence and determine whether the system is back on track.",
            "action_taken": action.to_dict(),
            "verification_evidence": evidence,
            "requirements": {
                "classify_recovered": True,
                "classify_root_cause_mitigated": True,
                "prefer not recovered when evidence is contradictory": True,
            },
        }
        parsed = self.llm.complete_json(
            name="verification_decision",
            schema={
                "type": "object",
                "properties": {
                    "recovered": {"type": "boolean"},
                    "root_cause_mitigated": {"type": "boolean"},
                    "after_summary": {"type": "string"},
                    "note": {"type": "string"},
                    "stages": {"type": "object", "additionalProperties": True},
                },
                "required": ["recovered", "root_cause_mitigated", "after_summary", "note", "stages"],
                "additionalProperties": False,
            },
            prompt=prompt,
        )
        before = evidence["before"]
        after = evidence["after"]
        return VerificationResult(
            recovered=bool(parsed.get("recovered", False)),
            root_cause_mitigated=bool(parsed.get("root_cause_mitigated", False)),
            before_incident_detected=bool(before["incident_detected"]),
            after_incident_detected=bool(after["incident_detected"]),
            before_summary=str(before["summary"]),
            after_summary=str(parsed.get("after_summary", after["summary"])),
            note=str(parsed.get("note", evidence["note"])),
            stages=dict(parsed.get("stages", {})),
            samples=list(evidence["samples"]),
            evidence=evidence,
        )
