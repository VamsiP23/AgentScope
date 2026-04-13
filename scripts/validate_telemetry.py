#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional
from urllib.error import URLError
from urllib.parse import urlencode, urlparse
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from runner_common import ensure_reusable_local_endpoint


def prom_query(prom_url: str, query: str, timeout: int = 10) -> Dict[str, Any]:
    url = f"{prom_url.rstrip('/')}/api/v1/query?{urlencode({'query': query})}"
    with urlopen(url, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus query failed: {payload}")
    return payload.get("data", {})


def prom_scalar_optional(prom_url: str, query: str) -> Optional[float]:
    data = prom_query(prom_url, query)
    results = data.get("result", [])
    if not results:
        return None
    try:
        return float(results[0].get("value", [0, "0"])[1])
    except (TypeError, ValueError):
        return None


def jaeger_services(jaeger_url: str, timeout: int = 10) -> List[str]:
    with urlopen(f"{jaeger_url.rstrip('/')}/api/services", timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return list(payload.get("data", []) or [])


def _presence_detail(ok: bool, present_text: str, missing_text: str, value: Any = None) -> str:
    if ok:
        suffix = f" ({value})" if value is not None else ""
        return f"{present_text}{suffix}"
    return missing_text


def _maybe_repair_local_endpoint(namespace: str, service_name: str, local_url: str, probe_path: str) -> Optional[str]:
    parsed = urlparse(local_url)
    host = (parsed.hostname or "").lower()
    if host not in {"localhost", "127.0.0.1"}:
        return None
    try:
        result = ensure_reusable_local_endpoint(namespace, service_name, local_url, probe_path)
        return f"repaired local {service_name} access ({result.get('mode', 'unknown')})"
    except Exception as exc:
        return f"unable to repair local {service_name} access: {exc}"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Validate telemetry sources required for AgentScope evidence collection.")
    p.add_argument("--prom-url", default="http://localhost:9090")
    p.add_argument("--jaeger-url", default="http://localhost:16686")
    p.add_argument("--namespace", default="default")
    p.add_argument("--require-services", default="frontend,checkoutservice")
    p.add_argument("--wait-seconds", type=int, default=30)
    p.add_argument("--poll-seconds", type=int, default=5)
    return p


def main() -> int:
    args = build_parser().parse_args()
    required_services = [item.strip() for item in args.require_services.split(",") if item.strip()]
    deadline = time.time() + max(1, args.wait_seconds)
    last_report: Dict[str, Any] = {}

    while True:
        checks: Dict[str, Dict[str, Any]] = {}
        failures: List[str] = []

        _maybe_repair_local_endpoint(args.namespace, "prometheus", args.prom_url, "/-/ready")

        def add_check(name: str, ok: bool, value: Any = None, detail: str = "") -> None:
            checks[name] = {"ok": ok, "value": value, "detail": detail}
            if not ok:
                failures.append(name if not detail else f"{name}: {detail}")

        try:
            otel_up = prom_scalar_optional(args.prom_url, 'sum(up{job="otel-collector-spanmetrics"})')
            ok = (otel_up or 0.0) >= 1.0
            add_check(
                "otel_spanmetrics_up",
                ok,
                otel_up,
                _presence_detail(ok, "otel spanmetrics scrape target reachable", "otel spanmetrics scrape target unavailable", otel_up),
            )
        except Exception as exc:
            add_check("otel_spanmetrics_up", False, None, str(exc))

        try:
            ksm_up = prom_scalar_optional(args.prom_url, 'sum(up{job="kube-state-metrics"})')
            ok = (ksm_up or 0.0) >= 1.0
            add_check(
                "kube_state_metrics_up",
                ok,
                ksm_up,
                _presence_detail(ok, "kube-state-metrics scrape target reachable", "kube-state-metrics scrape target unavailable", ksm_up),
            )
        except Exception as exc:
            add_check("kube_state_metrics_up", False, None, str(exc))

        try:
            cadvisor_up = prom_scalar_optional(args.prom_url, 'sum(up{job="kubernetes-cadvisor"})')
            ok = (cadvisor_up or 0.0) >= 1.0
            add_check(
                "cadvisor_up",
                ok,
                cadvisor_up,
                _presence_detail(ok, "cAdvisor scrape target reachable", "cAdvisor scrape target unavailable", cadvisor_up),
            )
        except Exception as exc:
            add_check("cadvisor_up", False, None, str(exc))

        try:
            cpu_series = prom_scalar_optional(
                args.prom_url,
                f'count(container_cpu_usage_seconds_total{{namespace="{args.namespace}",pod!=""}})',
            )
            ok = (cpu_series or 0.0) > 0.0
            add_check(
                "cpu_series_present",
                ok,
                cpu_series,
                _presence_detail(ok, "container CPU series present", "container CPU series missing", cpu_series),
            )
        except Exception as exc:
            add_check("cpu_series_present", False, None, str(exc))

        try:
            mem_series = prom_scalar_optional(
                args.prom_url,
                f'count(container_memory_working_set_bytes{{namespace="{args.namespace}",pod!=""}})',
            )
            ok = (mem_series or 0.0) > 0.0
            add_check(
                "memory_series_present",
                ok,
                mem_series,
                _presence_detail(ok, "container memory series present", "container memory series missing", mem_series),
            )
        except Exception as exc:
            add_check("memory_series_present", False, None, str(exc))

        try:
            limit_series = prom_scalar_optional(
                args.prom_url,
                f'count(kube_pod_container_resource_limits{{namespace="{args.namespace}",resource="cpu"}})',
            )
            ok = (limit_series or 0.0) > 0.0
            add_check(
                "cpu_limit_series_present",
                ok,
                limit_series,
                _presence_detail(ok, "CPU limit series present", "CPU limit series missing", limit_series),
            )
        except Exception as exc:
            add_check("cpu_limit_series_present", False, None, str(exc))

        try:
            request_series = prom_scalar_optional(
                args.prom_url,
                f'count(kube_pod_container_resource_requests{{namespace="{args.namespace}",resource="memory"}})',
            )
            ok = (request_series or 0.0) > 0.0
            add_check(
                "memory_request_series_present",
                ok,
                request_series,
                _presence_detail(ok, "memory request series present", "memory request series missing", request_series),
            )
        except Exception as exc:
            add_check("memory_request_series_present", False, None, str(exc))

        try:
            services = jaeger_services(args.jaeger_url)
            missing = [svc for svc in required_services if svc not in services]
            ok = not missing
            add_check(
                "jaeger_services",
                ok,
                services[:20],
                (
                    f"Jaeger reachable; discovered required services ({', '.join(required_services)})"
                    if ok
                    else f"Jaeger reachable, but missing services: {', '.join(missing)}"
                ),
            )
        except (URLError, RuntimeError, TimeoutError) as exc:
            repair_detail = _maybe_repair_local_endpoint(args.namespace, "jaeger", args.jaeger_url, "/api/services")
            if repair_detail and repair_detail.startswith("repaired"):
                try:
                    services = jaeger_services(args.jaeger_url)
                    missing = [svc for svc in required_services if svc not in services]
                    ok = not missing
                    add_check(
                        "jaeger_services",
                        ok,
                        services[:20],
                        (
                            f"{repair_detail}; discovered required services"
                            if ok
                            else f"{repair_detail}; Jaeger reachable, but missing services: {', '.join(missing)}"
                        ),
                    )
                except Exception as retry_exc:
                    add_check(
                        "jaeger_services",
                        False,
                        None,
                        f"Jaeger unreachable at {args.jaeger_url}: {retry_exc} ({repair_detail})",
                    )
            else:
                detail = f"Jaeger unreachable at {args.jaeger_url}: {exc}"
                if repair_detail:
                    detail = f"{detail} ({repair_detail})"
                add_check("jaeger_services", False, None, detail)
        except Exception as exc:
            add_check("jaeger_services", False, None, f"Jaeger validation failed: {exc}")

        last_report = {
            "checked_at_epoch": time.time(),
            "checks": checks,
            "ok": not failures,
            "failures": failures,
        }

        if not failures:
            print(json.dumps(last_report, indent=2))
            return 0

        if time.time() >= deadline:
            print(json.dumps(last_report, indent=2))
            return 1

        time.sleep(max(1, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
