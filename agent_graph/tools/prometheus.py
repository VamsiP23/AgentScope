from __future__ import annotations

import re
from typing import Any, Dict, List

from detectors.prometheus import PrometheusClient as DetectorPrometheusClient


class PrometheusTools:
    def __init__(self, prom_url: str) -> None:
        self.client = DetectorPrometheusClient(prom_url)

    def global_error_ratio(self, window: str) -> Dict[str, float]:
        return self.client.global_error_ratio(window)

    def top_error_services(self, window: str, limit: int = 5) -> List[Dict[str, Any]]:
        return self.client.top_error_services(window, limit=limit)

    def service_rps(self, window: str, limit: int = 10) -> List[Dict[str, Any]]:
        rows = self.client.vector(f"sum(rate(calls_total[{window}])) by (service_name)")
        parsed: List[Dict[str, Any]] = []
        for row in rows:
            parsed.append(
                {
                    "service_name": row.get("metric", {}).get("service_name", "unknown"),
                    "rps": float(row.get("value", [0, "0"])[1]),
                }
            )
        parsed.sort(key=lambda item: item["rps"], reverse=True)
        return parsed[:limit]

    def service_metrics(self, namespace: str, service: str, lookback_minutes: int = 5) -> Dict[str, Any]:
        window = f"{max(1, lookback_minutes)}m"
        pod_regex = f"{re.escape(service)}-.*"
        errors: List[str] = []

        cpu_cores = self._safe_optional_scalar(
            (
                "sum(rate(container_cpu_usage_seconds_total"
                f'{{namespace="{namespace}",pod=~"{pod_regex}",container!="",image!=""}}[{window}]))'
            ),
            errors,
            "cpu_usage",
        )
        cpu_mcores = (cpu_cores or 0.0) * 1000.0 if cpu_cores is not None else None
        cpu_request_cores = self._safe_optional_scalar(
            (
                "sum(kube_pod_container_resource_requests"
                f'{{namespace="{namespace}",pod=~"{pod_regex}",resource="cpu"}})'
            ),
            errors,
            "cpu_request",
        )
        cpu_limit_cores = self._safe_optional_scalar(
            (
                "sum(kube_pod_container_resource_limits"
                f'{{namespace="{namespace}",pod=~"{pod_regex}",resource="cpu"}})'
            ),
            errors,
            "cpu_limit",
        )
        cpu_throttled_seconds_rate = self._safe_optional_scalar(
            (
                "sum(rate(container_cpu_cfs_throttled_seconds_total"
                f'{{namespace="{namespace}",pod=~"{pod_regex}",container!="",image!=""}}[{window}]))'
            ),
            errors,
            "cpu_throttled_seconds_rate",
        )
        cpu_throttled_periods_rate = self._safe_optional_scalar(
            (
                "sum(rate(container_cpu_cfs_throttled_periods_total"
                f'{{namespace="{namespace}",pod=~"{pod_regex}",container!="",image!=""}}[{window}]))'
            ),
            errors,
            "cpu_throttled_periods_rate",
        )
        cpu_periods_rate = self._safe_optional_scalar(
            (
                "sum(rate(container_cpu_cfs_periods_total"
                f'{{namespace="{namespace}",pod=~"{pod_regex}",container!="",image!=""}}[{window}]))'
            ),
            errors,
            "cpu_periods_rate",
        )
        memory_bytes = self._safe_optional_scalar(
            (
                "sum(container_memory_working_set_bytes"
                f'{{namespace="{namespace}",pod=~"{pod_regex}",container!="",image!=""}})'
            ),
            errors,
            "memory_usage",
        )
        memory_rss_bytes = self._safe_optional_scalar(
            (
                "sum(container_memory_rss"
                f'{{namespace="{namespace}",pod=~"{pod_regex}",container!="",image!=""}})'
            ),
            errors,
            "memory_rss",
        )
        memory_request_bytes = self._safe_optional_scalar(
            (
                "sum(kube_pod_container_resource_requests"
                f'{{namespace="{namespace}",pod=~"{pod_regex}",resource="memory"}})'
            ),
            errors,
            "memory_request",
        )
        memory_limit_bytes = self._safe_optional_scalar(
            (
                "sum(kube_pod_container_resource_limits"
                f'{{namespace="{namespace}",pod=~"{pod_regex}",resource="memory"}})'
            ),
            errors,
            "memory_limit",
        )
        request_rps = self._safe_optional_scalar(
            f'sum(rate(calls_total{{service_name="{service}"}}[{window}]))',
            errors,
            "request_rps",
        )
        error_rps = self._safe_optional_scalar(
            f'sum(rate(calls_total{{service_name="{service}",status_code="STATUS_CODE_ERROR"}}[{window}]))',
            errors,
            "error_rps",
        )
        p95_latency_ms = self._safe_latency_quantile(service, window, 0.95, errors, "latency_p95")
        p99_latency_ms = self._safe_latency_quantile(service, window, 0.99, errors, "latency_p99")

        resource_metric_gaps = [
            name
            for name, value in {
                "cpu_usage": cpu_cores,
                "cpu_request_cores": cpu_request_cores,
                "cpu_limit_cores": cpu_limit_cores,
                "cpu_throttled_seconds_rate": cpu_throttled_seconds_rate,
                "memory_usage": memory_bytes,
                "memory_request_bytes": memory_request_bytes,
                "memory_limit_bytes": memory_limit_bytes,
            }.items()
            if value is None
        ]
        application_metric_gaps = [
            name
            for name, value in {
                "request_rps": request_rps,
                "error_rps": error_rps,
                "p95_latency_ms": p95_latency_ms,
                "p99_latency_ms": p99_latency_ms,
            }.items()
            if value is None
        ]

        return {
            "service": service,
            "lookback_minutes": lookback_minutes,
            "cpu_cores": cpu_cores,
            "cpu_mcores": cpu_mcores,
            "cpu_request_cores": cpu_request_cores,
            "cpu_limit_cores": cpu_limit_cores,
            "cpu_utilization_pct_of_request": self._safe_percent(cpu_cores, cpu_request_cores),
            "cpu_utilization_pct_of_limit": self._safe_percent(cpu_cores, cpu_limit_cores),
            "cpu_headroom_cores_to_limit": (
                max((cpu_limit_cores or 0.0) - (cpu_cores or 0.0), 0.0) if cpu_limit_cores is not None and cpu_cores is not None and cpu_limit_cores > 0 else None
            ),
            "cpu_throttled_seconds_rate": cpu_throttled_seconds_rate,
            "cpu_throttled_periods_rate": cpu_throttled_periods_rate,
            "cpu_periods_rate": cpu_periods_rate,
            "cpu_throttling_ratio": self._safe_ratio(cpu_throttled_periods_rate, cpu_periods_rate),
            "memory_bytes": memory_bytes,
            "memory_rss_bytes": memory_rss_bytes,
            "memory_mib": (memory_bytes / (1024 * 1024)) if memory_bytes is not None else None,
            "memory_rss_mib": (memory_rss_bytes / (1024 * 1024)) if memory_rss_bytes is not None else None,
            "memory_request_bytes": memory_request_bytes,
            "memory_limit_bytes": memory_limit_bytes,
            "memory_request_mib": (memory_request_bytes / (1024 * 1024)) if memory_request_bytes is not None else None,
            "memory_limit_mib": (memory_limit_bytes / (1024 * 1024)) if memory_limit_bytes is not None else None,
            "memory_utilization_pct_of_request": self._safe_percent(memory_bytes, memory_request_bytes),
            "memory_utilization_pct_of_limit": self._safe_percent(memory_bytes, memory_limit_bytes),
            "memory_headroom_bytes_to_limit": (
                max((memory_limit_bytes or 0.0) - (memory_bytes or 0.0), 0.0) if memory_limit_bytes is not None and memory_bytes is not None and memory_limit_bytes > 0 else None
            ),
            "request_rps": request_rps,
            "error_rps": error_rps,
            "error_rate": (error_rps / request_rps) if request_rps is not None and error_rps is not None and request_rps > 0 else None,
            "latency_p95_ms": p95_latency_ms,
            "latency_p99_ms": p99_latency_ms,
            "resource_metrics_available": not resource_metric_gaps,
            "application_metrics_available": not application_metric_gaps,
            "resource_metric_gaps": resource_metric_gaps,
            "application_metric_gaps": application_metric_gaps,
            "error": "; ".join(errors) if errors else None,
        }

    def _safe_scalar(self, query: str, errors: List[str], label: str) -> float:
        try:
            return float(self.client.instant_scalar(query))
        except Exception as exc:
            errors.append(f"{label}: {exc}")
            return 0.0

    def _safe_optional_scalar(self, query: str, errors: List[str], label: str) -> float | None:
        try:
            return self.client.instant_scalar_optional(query)
        except Exception as exc:
            errors.append(f"{label}: {exc}")
            return None

    def _safe_latency_quantile(
        self,
        service: str,
        window: str,
        quantile: float,
        errors: List[str],
        label: str,
    ) -> float | None:
        try:
            return float(self.client.service_latency_ms(window, service, quantile))
        except Exception as exc:
            errors.append(f"{label}: {exc}")
            return None

    def _safe_ratio(self, numerator: float | None, denominator: float | None) -> float | None:
        if numerator is None or denominator is None or denominator <= 0:
            return None
        return numerator / denominator

    def _safe_percent(self, numerator: float | None, denominator: float | None) -> float | None:
        ratio = self._safe_ratio(numerator, denominator)
        if ratio is None:
            return None
        return 100.0 * ratio
