from __future__ import annotations

from typing import Any, Dict, List

from benchmarking.problem import ProblemSpec


DEFAULT_REQUIRED_CHECKS = [
    "otel_spanmetrics_up",
    "kube_state_metrics_up",
    "cadvisor_up",
    "cpu_series_present",
    "memory_series_present",
    "cpu_limit_series_present",
    "memory_request_series_present",
]


def evaluate_telemetry_contract(problem: ProblemSpec | None, validation_step: Dict[str, Any]) -> Dict[str, Any]:
    report = dict(validation_step.get("report", {}) or {})
    checks = dict(report.get("checks", {}) or {})

    if problem is None:
        return {
            "ok": True,
            "required_checks": list(DEFAULT_REQUIRED_CHECKS),
            "failed_checks": [],
            "required_services": [],
            "notes": "no benchmark problem mapped for this experiment; telemetry validation is advisory",
        }

    required_checks = list(problem.telemetry_contract.required_validation_checks or DEFAULT_REQUIRED_CHECKS)
    failed_checks: List[str] = []
    for check_name in required_checks:
        if not bool((checks.get(check_name, {}) or {}).get("ok", False)):
            failed_checks.append(check_name)

    ok = not failed_checks
    if problem.telemetry_contract.fail_open:
        ok = True

    return {
        "ok": ok,
        "required_checks": required_checks,
        "failed_checks": failed_checks,
        "required_services": list(problem.telemetry_contract.required_services),
        "notes": problem.telemetry_contract.notes,
    }
