from __future__ import annotations

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
