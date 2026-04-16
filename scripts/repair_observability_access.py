#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from runner_common import ensure_reusable_local_endpoint  # noqa: E402


def _get_json(url: str, timeout: int = 10) -> Dict[str, Any]:
    with urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _prom_query(prom_url: str, query: str) -> Dict[str, Any]:
    return _get_json(f"{prom_url.rstrip('/')}/api/v1/query?{urlencode({'query': query})}")


def _scalar(prom_url: str, query: str) -> float | None:
    payload = _prom_query(prom_url, query)
    rows = payload.get("data", {}).get("result", [])
    if not rows:
        return None
    try:
        return float(rows[0].get("value", [0, "0"])[1])
    except (TypeError, ValueError):
        return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Repair and validate local access to AgentScope observability services.")
    parser.add_argument("--namespace", default="default")
    parser.add_argument("--prom-url", default="http://localhost:9090")
    parser.add_argument("--jaeger-url", default="http://localhost:16686")
    parser.add_argument("--frontend-url", default="http://localhost:8080")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report: Dict[str, Any] = {"checks": {}, "ok": True}

    def add(name: str, ok: bool, detail: Any) -> None:
        report["checks"][name] = {"ok": ok, "detail": detail}
        if not ok:
            report["ok"] = False

    try:
        add(
            "prometheus_access",
            True,
            ensure_reusable_local_endpoint(args.namespace, "prometheus", args.prom_url, "/-/ready"),
        )
    except Exception as exc:
        add("prometheus_access", False, str(exc))

    try:
        add(
            "jaeger_access",
            True,
            ensure_reusable_local_endpoint(args.namespace, "jaeger", args.jaeger_url, "/api/services"),
        )
    except Exception as exc:
        add("jaeger_access", False, str(exc))

    try:
        add(
            "frontend_access",
            True,
            ensure_reusable_local_endpoint(
                args.namespace,
                "frontend-external",
                args.frontend_url,
                "/_healthz",
                remote_port=80,
            ),
        )
    except Exception as exc:
        add("frontend_access", False, str(exc))

    if report["checks"].get("prometheus_access", {}).get("ok"):
        for name, query in {
            "otel_spanmetrics_up": 'sum(up{job="otel-collector-spanmetrics"})',
            "kube_state_metrics_up": 'sum(up{job="kube-state-metrics"})',
            "cadvisor_up": 'sum(up{job="kubernetes-cadvisor"})',
            "cpu_series_present": f'count(container_cpu_usage_seconds_total{{namespace="{args.namespace}",pod!=""}})',
            "memory_series_present": f'count(container_memory_working_set_bytes{{namespace="{args.namespace}",pod!=""}})',
            "cpu_limit_series_present": f'count(kube_pod_container_resource_limits{{namespace="{args.namespace}",resource="cpu"}})',
        }.items():
            try:
                value = _scalar(args.prom_url, query)
                add(name, bool((value or 0.0) > 0.0), value)
            except Exception as exc:
                add(name, False, str(exc))

    if report["checks"].get("jaeger_access", {}).get("ok"):
        try:
            services = _get_json(f"{args.jaeger_url.rstrip('/')}/api/services").get("data", [])
            add("jaeger_services", bool(services), services[:30])
        except Exception as exc:
            add("jaeger_services", False, str(exc))

    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
