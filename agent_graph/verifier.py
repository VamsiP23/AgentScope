from __future__ import annotations

import time
from typing import Any, Dict, List

from agent_graph.schemas import ActionPlan, VerificationResult
from agent_graph.tools.kubernetes import KubernetesTools
from detectors.monitor import build_report
from detectors.schemas import DetectionConfig


class Verifier:
    def __init__(self, config: DetectionConfig, wait_seconds: int = 60, poll_interval_seconds: int = 10) -> None:
        self.config = config
        self.wait_seconds = wait_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.k8s = KubernetesTools()

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
        return {
            "report": report,
            "deployment": deployment,
            "pod_status": pod_status,
            "error_ratio": self._extract_metric(report, "error_ratio"),
            "service_error_rps": self._extract_metric(report, "service_error_rate"),
            "summary": report.get("summary", ""),
        }

    def run(self, action: ActionPlan, detection_before: dict) -> VerificationResult:
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
        latest_report = latest["report"]
        deployment = latest["deployment"]
        pod_status = latest["pod_status"]

        before_error_ratio = self._extract_metric(detection_before, "error_ratio")
        before_service_error_rps = self._extract_metric(detection_before, "service_error_rate")
        max_observed_error_ratio = max(sample["error_ratio"] for sample in samples)
        max_observed_service_error_rps = max(sample["service_error_rps"] for sample in samples)

        stages: Dict[str, Any] = {}
        root_cause_mitigated = False

        if action.action == "restore_replicas":
            desired_restored = int(deployment.get("desired", 0)) >= 1
            pod_exists = int(pod_status.get("pod_count", 0)) >= 1
            rollout_progressing = bool(pod_status.get("pod_count", 0)) and (
                bool(deployment.get("available", 0))
                or bool(pod_status.get("progressing", False))
                or bool(pod_status.get("ready_pod_count", 0))
            )
            available_recovered = int(deployment.get("available", 0)) >= 1
            errors_declining = (
                available_recovered
                and latest["error_ratio"] <= max(before_error_ratio, max_observed_error_ratio)
                and latest["service_error_rps"] <= max(before_service_error_rps, max_observed_service_error_rps)
            )
            if max_observed_error_ratio > 0:
                errors_declining = errors_declining and latest["error_ratio"] < max_observed_error_ratio
            if max_observed_service_error_rps > 0:
                errors_declining = errors_declining and latest["service_error_rps"] < max_observed_service_error_rps

            stages = {
                "desired_restored": desired_restored,
                "pod_exists": pod_exists,
                "rollout_progressing": rollout_progressing,
                "available_recovered": available_recovered,
                "errors_declining": errors_declining,
                "final_desired": deployment.get("desired", 0),
                "final_available": deployment.get("available", 0),
                "final_pod_count": pod_status.get("pod_count", 0),
                "final_ready_pod_count": pod_status.get("ready_pod_count", 0),
            }
            root_cause_mitigated = all(
                [
                    desired_restored,
                    pod_exists,
                    rollout_progressing,
                    available_recovered,
                    errors_declining,
                ]
            )
            recovered = root_cause_mitigated and not latest_report.get("incident_detected", False)
        elif action.action == "wait_and_recheck":
            incident_cleared = initial_incident and not latest_report.get("incident_detected", False)
            deployment_healthy = bool(deployment.get("healthy", False))
            errors_declining = latest["error_ratio"] <= before_error_ratio and latest["service_error_rps"] <= before_service_error_rps
            root_cause_mitigated = deployment_healthy or errors_declining
            recovered = incident_cleared
            stages = {
                "incident_cleared": incident_cleared,
                "deployment_healthy": deployment_healthy,
                "errors_declining": errors_declining,
                "final_desired": deployment.get("desired", 0),
                "final_available": deployment.get("available", 0),
                "final_pod_count": pod_status.get("pod_count", 0),
                "final_ready_pod_count": pod_status.get("ready_pod_count", 0),
            }
        else:
            recovered = initial_incident and not latest_report.get("incident_detected", False)
            root_cause_mitigated = recovered
            stages = {
                "incident_cleared": recovered,
                "final_desired": deployment.get("desired", 0),
                "final_available": deployment.get("available", 0),
                "final_pod_count": pod_status.get("pod_count", 0),
                "final_ready_pod_count": pod_status.get("ready_pod_count", 0),
            }

        note = (
            f"verification polled every {poll}s for {total_wait}s"
            if total_wait > 0
            else "verification used immediate recheck"
        )

        sample_summaries = [
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
        ]

        return VerificationResult(
            root_cause_mitigated=root_cause_mitigated,
            before_incident_detected=initial_incident,
            after_incident_detected=latest_report.get("incident_detected", False),
            before_summary=detection_before.get("summary", ""),
            after_summary=latest_report.get("summary", ""),
            recovered=recovered,
            note=note,
            stages=stages,
            samples=sample_summaries,
        )
