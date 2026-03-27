from __future__ import annotations

from typing import Any, Dict, List

from detectors.utils import prom_query


class PrometheusClient:
    def __init__(self, prom_url: str) -> None:
        self.prom_url = prom_url

    def instant_scalar(self, query: str) -> float:
        data = prom_query(self.prom_url, query)
        results = data.get("result", [])
        if not results:
            return 0.0
        value = results[0].get("value", [0, "0"])[1]
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def vector(self, query: str) -> List[Dict[str, Any]]:
        data = prom_query(self.prom_url, query)
        return data.get("result", [])

    def global_error_ratio(self, window: str) -> Dict[str, float]:
        total_rps = self.instant_scalar(f"sum(rate(calls_total[{window}]))")
        error_rps = self.instant_scalar(
            f'sum(rate(calls_total{{status_code="STATUS_CODE_ERROR"}}[{window}]))'
        )
        return {
            "total_rps": total_rps,
            "error_rps": error_rps,
            "error_ratio": (error_rps / total_rps) if total_rps > 0 else 0.0,
        }

    def top_error_services(self, window: str, limit: int = 10) -> List[Dict[str, Any]]:
        rows = self.vector(
            f'sum(rate(calls_total{{status_code="STATUS_CODE_ERROR"}}[{window}])) by (service_name)'
        )
        parsed: List[Dict[str, Any]] = []
        for row in rows:
            parsed.append(
                {
                    "service_name": row.get("metric", {}).get("service_name", "unknown"),
                    "error_rps": float(row.get("value", [0, "0"])[1]),
                }
            )
        parsed.sort(key=lambda item: item["error_rps"], reverse=True)
        return parsed[:limit]

    def service_p99_latency_ms(self, window: str, service_name: str) -> float:
        queries = [
            (
                "histogram_quantile(0.99, "
                f"sum(rate(duration_milliseconds_bucket{{service_name=\"{service_name}\"}}[{window}])) by (le))"
            ),
            (
                "histogram_quantile(0.99, "
                f"sum(rate(duration_bucket{{service_name=\"{service_name}\"}}[{window}])) by (le))"
            ),
            (
                "histogram_quantile(0.99, "
                f"sum(rate(latency_bucket{{service_name=\"{service_name}\"}}[{window}])) by (le))"
            ),
        ]
        for query in queries:
            value = self.instant_scalar(query)
            if value > 0:
                return value
        return 0.0
