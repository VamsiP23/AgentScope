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

    def service_latency_detector(self) -> DetectorFinding:
        if not self.config.target_deployment:
            return DetectorFinding(
                name="service_latency",
                triggered=False,
                severity="info",
                reason="no target deployment configured",
            )
        p99_latency_ms = self.prom.service_p99_latency_ms(
            self.config.window,
            self.config.target_deployment,
        )
        triggered = p99_latency_ms >= self.config.service_latency_threshold_ms
        severity = "high" if triggered else "info"
        reason = (
            f"service {self.config.target_deployment} p99 latency {p99_latency_ms:.3f} ms"
        )
        return DetectorFinding(
            name="service_latency",
            triggered=triggered,
            severity=severity,
            reason=reason,
            service=self.config.target_deployment,
            value=round(p99_latency_ms, 6),
            threshold=self.config.service_latency_threshold_ms,
            details={
                "service_name": self.config.target_deployment,
                "p99_latency_ms": p99_latency_ms,
            },
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
            f"deployment {self.config.target_deployment} available={dep.get('available', 0)} "
            f"updated={dep.get('updated', 0)} unavailable={dep.get('unavailable', 0)} "
            f"desired={dep.get('desired', 0)}"
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

    def service_endpoints_detector(self) -> DetectorFinding:
        if not self.config.target_deployment:
            return DetectorFinding(
                name="service_endpoints",
                triggered=False,
                severity="info",
                reason="no target service configured",
            )
        endpoints = self.k8s.service_endpoint_health(self.config.namespace, self.config.target_deployment)
        triggered = endpoints.get("exists", False) and int(endpoints.get("ready_addresses", 0)) == 0
        severity = "high" if triggered else "info"
        reason = (
            f"service {self.config.target_deployment} ready_endpoints="
            f"{endpoints.get('ready_addresses', 0)} not_ready_endpoints={endpoints.get('not_ready_addresses', 0)}"
        )
        return DetectorFinding(
            name="service_endpoints",
            triggered=triggered,
            severity=severity,
            reason=reason,
            service=self.config.target_deployment,
            value=int(endpoints.get("ready_addresses", 0)),
            threshold=1,
            details=endpoints,
        )

    def service_port_alignment_detector(self) -> DetectorFinding:
        if not self.config.target_deployment:
            return DetectorFinding(
                name="service_port_alignment",
                triggered=False,
                severity="info",
                reason="no target service configured",
            )
        alignment = self.k8s.service_port_alignment(self.config.namespace, self.config.target_deployment)
        triggered = alignment.get("exists", False) and not alignment.get("aligned", True)
        severity = "high" if triggered else "info"
        mismatches = alignment.get("mismatches", [])
        reason = (
            f"service {self.config.target_deployment} port alignment "
            f"{'mismatch' if triggered else 'ok'}"
        )
        if mismatches:
            reason += f": {mismatches}"
        return DetectorFinding(
            name="service_port_alignment",
            triggered=triggered,
            severity=severity,
            reason=reason,
            service=self.config.target_deployment,
            value=len(mismatches),
            threshold=0,
            details=alignment,
        )

    def native_stress_job_detector(self) -> DetectorFinding:
        jobs = self.k8s.active_native_stress_jobs(self.config.namespace)
        triggered = bool(jobs)
        severity = "high" if triggered else "info"
        reason = (
            f"active native stress jobs: {', '.join(item['job'] or item['pod'] for item in jobs)}"
            if jobs
            else "no active native stress jobs"
        )
        return DetectorFinding(
            name="native_stress_job",
            triggered=triggered,
            severity=severity,
            reason=reason,
            service=self.config.target_deployment,
            value=len(jobs),
            threshold=0,
            details={"active_stress_jobs": jobs},
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

    def _safe_detector(self, name: str, fn) -> DetectorFinding:
        try:
            return fn()
        except Exception as exc:
            return DetectorFinding(
                name=name,
                triggered=False,
                severity="warning",
                reason=f"{name} failed: {exc}",
                details={"error": str(exc)},
            )

    def run(self) -> List[DetectorFinding]:
        return [
            self._safe_detector("error_ratio", self.error_ratio_detector),
            self._safe_detector("service_error_rate", self.service_error_rate_detector),
            self._safe_detector("service_latency", self.service_latency_detector),
            self._safe_detector("deployment_availability", self.availability_detector),
            self._safe_detector("service_endpoints", self.service_endpoints_detector),
            self._safe_detector("service_port_alignment", self.service_port_alignment_detector),
            self._safe_detector("native_stress_job", self.native_stress_job_detector),
            self._safe_detector("restart_history", self.restart_history_detector),
        ]
