from __future__ import annotations

from typing import List

from detectors.kubernetes import KubernetesClient
from detectors.prometheus import PrometheusClient
from detectors.schemas import DetectionConfig, DetectorFinding


class DetectorRunner:
    def __init__(self, config: DetectionConfig) -> None:
        self.config = config
        self.prom = PrometheusClient(config.prom_url)
        self.k8s = KubernetesClient()

    def error_ratio_detector(self) -> DetectorFinding:
        metric = self.prom.global_error_ratio(self.config.window)
        triggered = (
            metric["total_rps"] >= self.config.min_total_rps
            and metric["error_ratio"] >= self.config.error_ratio_threshold
        )
        severity = "high" if triggered else "info"
        reason = (
            f"global error ratio {metric['error_ratio']:.3f} with total_rps={metric['total_rps']:.3f}"
        )
        return DetectorFinding(
            name="error_ratio",
            triggered=triggered,
            severity=severity,
            reason=reason,
            value=round(metric["error_ratio"], 6),
            threshold=self.config.error_ratio_threshold,
            details=metric,
        )

    def service_error_rate_detector(self) -> DetectorFinding:
        top = self.prom.top_error_services(self.config.window, limit=1)
        if not top:
            return DetectorFinding(
                name="service_error_rate",
                triggered=False,
                severity="info",
                reason="no service-level error series returned",
            )
        top_service = top[0]
        triggered = top_service["error_rps"] >= self.config.service_error_rps_threshold
        severity = "high" if triggered else "info"
        reason = (
            f"top error service {top_service['service_name']} at {top_service['error_rps']:.3f} rps"
        )
        return DetectorFinding(
            name="service_error_rate",
            triggered=triggered,
            severity=severity,
            reason=reason,
            service=top_service["service_name"],
            value=round(top_service["error_rps"], 6),
            threshold=self.config.service_error_rps_threshold,
            details={"top_error_services": top[:5]},
        )

    def availability_detector(self) -> DetectorFinding:
        if not self.config.target_deployment:
            return DetectorFinding(
                name="deployment_availability",
                triggered=False,
                severity="info",
                reason="no target deployment configured",
            )
        dep = self.k8s.deployment_health(self.config.namespace, self.config.target_deployment)
        triggered = not dep.get("healthy", False)
        severity = "critical" if triggered else "info"
        reason = (
            f"deployment {self.config.target_deployment} available={dep.get('available', 0)} desired={dep.get('desired', 0)}"
        )
        return DetectorFinding(
            name="deployment_availability",
            triggered=triggered,
            severity=severity,
            reason=reason,
            service=self.config.target_deployment,
            value=dep.get("available", 0),
            threshold=dep.get("desired", 0),
            details=dep,
        )

    def restart_history_detector(self) -> DetectorFinding:
        top = self.k8s.top_pod_restarts(self.config.namespace, limit=5)
        if not top:
            return DetectorFinding(
                name="restart_history",
                triggered=False,
                severity="info",
                reason="no pod restart history detected",
                details={"top_pod_restarts": []},
            )
        top_restart = top[0]
        triggered = False
        severity = "info"
        reason = (
            f"historical restart count observed on {top_restart['pod']} count={top_restart['restart_count']}"
        )
        return DetectorFinding(
            name="restart_history",
            triggered=triggered,
            severity=severity,
            reason=reason,
            service=top_restart["pod"],
            value=top_restart["restart_count"],
            threshold=self.config.restart_count_threshold,
            details={"top_pod_restarts": top},
        )

    def run(self) -> List[DetectorFinding]:
        return [
            self.error_ratio_detector(),
            self.service_error_rate_detector(),
            self.availability_detector(),
            self.restart_history_detector(),
        ]
