#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from benchmarking.problem import ProblemSpec, load_benchmark_suite  # noqa: E402
from benchmarking.replay import ReplayDataset  # noqa: E402
from runner_k8s import list_existing_native_fault_state, verify_environment  # noqa: E402


def repo_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return ROOT / path


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


LEAKY_CONTEXT_PATTERNS = [
    r"target\s*port\s*(?:=|:)?\s*\d+",
    r"selector\s*(?:=|:)",
    r"bad image",
    r"imagepull",
    r"errimagepull",
    r"bad probe",
    r"probe failure",
    r"scale(?:d)? to zero",
    r"replicas?\s*(?:=|:)?\s*0",
    r"cartservice:1",
    r"emailservice:1",
    r"emailservice:5999",
    r"cpu limit",
    r"memory limit",
    r"oom",
    r"stress job",
    r"pod delete",
    r"deleted pod",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compact_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def run(cmd: List[str], *, cwd: Path, log_path: Path) -> Dict[str, Any]:
    started = utc_now()
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "\n".join(
            [
                "COMMAND: " + " ".join(cmd),
                f"STARTED_AT_UTC: {started}",
                f"FINISHED_AT_UTC: {utc_now()}",
                f"RETURNCODE: {proc.returncode}",
                "",
                "STDOUT:",
                proc.stdout.rstrip(),
                "",
                "STDERR:",
                proc.stderr.rstrip(),
                "",
            ]
        )
    )
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "log": str(log_path),
    }


def problem_by_id(suite_path: Path, scenario_ids: List[str]) -> List[ProblemSpec]:
    suite = load_benchmark_suite(suite_path)
    problems: List[ProblemSpec] = []
    for scenario_id in scenario_ids:
        problem = suite.find_problem_by_id(scenario_id)
        if problem is None:
            raise RuntimeError(f"scenario not found in suite: {scenario_id}")
        if not problem.experiment_file:
            raise RuntimeError(f"scenario has no experiment_file: {scenario_id}")
        if not problem.experiment_file.exists():
            raise RuntimeError(f"experiment_file does not exist for {scenario_id}: {problem.experiment_file}")
        problems.append(problem)
    return problems


def episode_paths(problem_id: str) -> List[Path]:
    episode_dir = ROOT / "datasets" / "episodes" / problem_id
    if not episode_dir.exists():
        return []
    return sorted(episode_dir.glob(f"{problem_id}_*.json"))


def initial_context_text(payload: Dict[str, Any]) -> str:
    value = payload.get("initial_context", "")
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(str(v) for v in value.values())
    return str(value)


def has_leaky_initial_context(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    text = initial_context_text(payload).lower()
    hits = []
    for pattern in LEAKY_CONTEXT_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            hits.append(pattern)
    return bool(hits), hits


def phase_responses(payload: Dict[str, Any]) -> Dict[str, Any]:
    phases = list(payload.get("phases", []) or [])
    if not phases:
        return {}
    return dict((phases[0] or {}).get("tool_responses", {}) or {})


def response_for(responses: Dict[str, Any], tool: str, service: str) -> Dict[str, Any]:
    prefix = f"{tool}|service={service}"
    for key, value in responses.items():
        if str(key).startswith(prefix):
            return dict(value or {})
    return {}


def responses_for_tool(responses: Dict[str, Any], tool: str) -> List[Dict[str, Any]]:
    return [dict(value or {}) for key, value in responses.items() if str(key).startswith(f"{tool}|")]


def channel_coverage(payload: Dict[str, Any], problem: ProblemSpec) -> Dict[str, Any]:
    responses = phase_responses(payload)
    k8s = response_for(responses, "get_k8s_state", problem.target_service)
    logs = response_for(responses, "get_logs", problem.target_service)
    metrics = response_for(responses, "get_metrics", problem.target_service)
    traces = responses_for_tool(responses, "get_traces") + responses_for_tool(responses, "get_dependency_traces")
    provenance = dict(payload.get("provenance", {}) or {})
    source_run_dir_value = str(provenance.get("source_run_dir", ""))
    source_run_dir = repo_path(source_run_dir_value) if source_run_dir_value else Path()
    summary = load_json(source_run_dir / "summary.json") if source_run_dir.exists() else {}
    evidence = load_json(source_run_dir / "evidence_report.json") if source_run_dir.exists() else {}

    service_config = dict(k8s.get("service_config", {}) or {})
    service_config_summary = dict(k8s.get("service_config_summary", {}) or {})
    deployment_config = dict(k8s.get("deployment_config", {}) or {})
    metrics_payload = dict(metrics.get("metrics", {}) or {})

    return {
        "kubernetes_workload": bool(k8s and (k8s.get("pod_phases") or "desired_replicas" in k8s)),
        "service_config": bool(service_config or service_config_summary),
        "deployment_config": bool(deployment_config),
        "logs": bool(logs and (logs.get("lines") or logs.get("raw_output"))),
        "metrics": bool(metrics_payload),
        "traces": bool(traces),
        "dependency_traces": bool(responses_for_tool(responses, "get_dependency_traces")),
        "detector_metadata": bool(summary.get("steps", {}).get("detection") or evidence.get("detector_snapshot")),
        "traffic_fault_logs": bool(summary.get("steps", {}).get("traffic") and summary.get("steps", {}).get("fault_apply")),
        "cleanup_status": bool(summary.get("steps", {}).get("fault_revert", {}).get("returncode") == 0),
        "source_run_dir": repo_relative(source_run_dir) if source_run_dir else "",
    }


def decisive_audit(payload: Dict[str, Any], problem: ProblemSpec) -> Tuple[bool, List[str]]:
    responses = phase_responses(payload)
    k8s = response_for(responses, "get_k8s_state", problem.target_service)
    logs = response_for(responses, "get_logs", problem.target_service)
    metrics = response_for(responses, "get_metrics", problem.target_service)
    dep_traces = response_for(responses, "get_dependency_traces", problem.target_service)
    family = problem.task_family or problem.category
    failures: List[str] = []

    if not k8s:
        failures.append(f"missing get_k8s_state({problem.target_service})")
        return False, failures

    service_summary = dict(k8s.get("service_config_summary", {}) or {})
    service_config = dict(k8s.get("service_config", {}) or {})
    deployment_config = dict(k8s.get("deployment_config", {}) or {})
    anomalies = set(str(item) for item in (k8s.get("anomalies", []) or []))
    anomalies.update(str(item) for item in (service_summary.get("anomalies", []) or []))

    if family == "native_service_selector_mismatch":
        if "service_selector_matches_no_pods" not in anomalies:
            failures.append("selector mismatch anomaly not replay-visible")
        if not service_summary.get("deployment_pod_labels"):
            failures.append("deployment pod labels missing")
    elif family == "native_service_port_mismatch":
        if "service_target_port_mismatch" not in anomalies:
            failures.append("targetPort mismatch anomaly not replay-visible")
        alignment = dict(service_summary.get("service_port_alignment", {}) or {})
        if not alignment.get("mismatches"):
            failures.append("targetPort mismatch details missing")
    elif family == "native_bad_image_rollout":
        text = json.dumps(k8s).lower()
        if not any(marker in text for marker in ["imagepull", "errimagepull", "image pull", "pulling image"]):
            failures.append("image-pull evidence missing")
    elif family == "native_bad_probe_rollout":
        text = json.dumps(k8s).lower()
        if "unhealthy" not in text and "probe" not in text:
            failures.append("probe/readiness failure evidence missing")
    elif family == "native_scale_zero":
        desired = int(k8s.get("desired_replicas", -1) or 0)
        available = int(k8s.get("available_replicas", -1) or 0)
        if desired != 0 or available != 0:
            failures.append(f"scale-zero replica evidence missing: desired={desired} available={available}")
    elif family == "native_pod_delete":
        text = json.dumps(k8s).lower()
        if not any(marker in text for marker in ["deleted pod", "successfuldelete", "killing", "stopping container"]):
            failures.append("pod deletion/disturbance event evidence missing")
    elif family in {"native_cpu_limit_throttle", "native_memory_limit_oom", "native_cpu_pressure_stress_job", "native_memory_pressure_stress_job"}:
        metrics_payload = dict(metrics.get("metrics", {}) or {})
        if not metrics_payload:
            failures.append("resource metrics missing")
        metric_text = json.dumps(metrics_payload).lower()
        k8s_text = json.dumps(k8s).lower()
        if "cpu" in family and not any(key in metric_text for key in ["throttle", "cpu_limit_pct", "cpu_usage"]):
            failures.append("CPU/throttling metric fields missing")
        if "memory" in family and not any(key in metric_text for key in ["memory", "oom"]):
            failures.append("memory metric fields missing")
        if family == "native_memory_limit_oom" and not any(marker in (metric_text + k8s_text) for marker in ["oom", "killed", "restart"]):
            failures.append("OOM/restart evidence missing")
    elif family in {"native_dependency_bad_endpoint", "native_bad_env"}:
        env = list(deployment_config.get("env", []) or [])
        env_text = json.dumps(env).lower()
        if not env:
            failures.append("deployment env/config evidence missing")
        if family == "native_dependency_bad_endpoint" and "cart_service_addr" not in env_text:
            failures.append("CART_SERVICE_ADDR evidence missing")
        if family == "native_bad_env" and "email_service_addr" not in env_text:
            failures.append("EMAIL_SERVICE_ADDR evidence missing")
        if not logs:
            failures.append("dependency/env logs missing")
        if problem.ground_truth.traces_required and not dep_traces:
            failures.append("dependency traces missing")
    else:
        for required in problem.ground_truth.required_evidence:
            method, service = parse_required_tool(required)
            if method and service and not response_for(responses, method, service):
                failures.append(f"missing required evidence {required}")

    for required in problem.ground_truth.required_evidence:
        method, service = parse_required_tool(required)
        if method and service and not response_for(responses, method, service):
            failures.append(f"missing required evidence {required}")

    return not failures, failures


def parse_required_tool(value: str) -> Tuple[str, str]:
    match = re.match(r"([a-zA-Z0-9_]+)\(([^)]+)\)", value.strip())
    if not match:
        return "", ""
    return match.group(1), match.group(2).split(",", 1)[0].strip()


def audit_episode(path: Path, problem: ProblemSpec) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
        ReplayDataset.load(path)
    except Exception as exc:
        return {
            "path": str(path),
            "benchmark_ready": False,
            "reason": f"episode load failed: {exc}",
            "coverage": {},
            "failures": [str(exc)],
        }

    leaky, leak_hits = has_leaky_initial_context(payload)
    decisive_ok, failures = decisive_audit(payload, problem)
    coverage = channel_coverage(payload, problem)
    if leaky:
        failures.append(f"leaky initial_context patterns: {leak_hits}")
    if not coverage.get("cleanup_status"):
        failures.append("cleanup status missing or failed in source run")

    return {
        "path": str(path),
        "benchmark_ready": bool(decisive_ok and not leaky and coverage.get("cleanup_status")),
        "reason": "ok" if decisive_ok and not leaky and coverage.get("cleanup_status") else "; ".join(failures),
        "coverage": coverage,
        "failures": failures,
    }


def strict_good_existing(problem: ProblemSpec) -> List[Dict[str, Any]]:
    audits = [audit_episode(path, problem) for path in episode_paths(problem.problem_id)]
    return [audit for audit in audits if audit.get("benchmark_ready")]


def newest_run_dir(out_root: Path, before: set[Path]) -> Path | None:
    candidates = [
        path
        for path in out_root.iterdir()
        if path.is_dir()
        and path not in before
        and path.name != "bulk_logs"
        and (path / "summary.json").exists()
        and (path / "evidence_report.json").exists()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def write_summaries(out_root: Path, summary: Dict[str, Any]) -> None:
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "summary.json").write_text(json.dumps(summary, indent=2))
    lines = [
        "# Native Bulk Collection Summary",
        "",
        f"- started_at_utc: {summary.get('started_at_utc', '')}",
        f"- finished_at_utc: {summary.get('finished_at_utc', '')}",
        f"- target_count: {summary.get('target_count', '')}",
        f"- dry_run: {summary.get('dry_run', False)}",
        "",
        "| scenario | ready | attempts | collected | failed | status |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in summary.get("scenarios", []):
        lines.append(
            "| {scenario} | {ready} | {attempts} | {collected} | {failed} | {status} |".format(
                scenario=item.get("scenario", ""),
                ready=item.get("ready_count", 0),
                attempts=len(item.get("attempts", [])),
                collected=len(item.get("collected", [])),
                failed=len(item.get("failed", [])),
                status=item.get("status", ""),
            )
        )
    lines.append("")
    lines.append("## Failed/Skipped Details")
    for item in summary.get("scenarios", []):
        for failure in item.get("failed", []):
            lines.append(f"- {item.get('scenario')}: {failure.get('reason', 'failed')}")
        if item.get("status") != "target_met":
            lines.append(f"- {item.get('scenario')}: {item.get('status')}")
    (out_root / "summary.md").write_text("\n".join(lines) + "\n")


def cleanup_check(namespace: str) -> Dict[str, Any]:
    verify_environment(namespace)
    remaining = list_existing_native_fault_state(namespace)
    if remaining:
        raise RuntimeError(f"native fault resources still active: {', '.join(remaining)}")
    return {"ok": True, "remaining_native_fault_resources": [], "checked_at_utc": utc_now()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bulk collect native benchmark episodes with deterministic evidence audits.")
    parser.add_argument("--suite", default=str(ROOT / "benchmark_suite.yaml"))
    parser.add_argument("--scenarios", nargs="+", required=True)
    parser.add_argument("--target-count", type=int, default=3)
    parser.add_argument("--out-root", default=str(ROOT / "results" / "native_episode_collection" / f"bulk_{compact_ts()}"))
    parser.add_argument("--difficulty", default="medium")
    parser.add_argument("--namespace", default="default")
    parser.add_argument("--lookback-minutes", type=int, default=5)
    parser.add_argument("--max-attempts-per-scenario", type=int, default=5)
    parser.add_argument("--warm-cluster", action="store_true", default=True)
    parser.add_argument("--no-warm-cluster", action="store_false", dest="warm_cluster")
    parser.add_argument("--include-dependencies", action="store_true")
    parser.add_argument("--audit-evidence", action="store_true", default=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    suite_path = Path(args.suite).resolve()
    out_root = Path(args.out_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    problems = problem_by_id(suite_path, list(args.scenarios))

    summary: Dict[str, Any] = {
        "started_at_utc": utc_now(),
        "suite": str(suite_path),
        "out_root": str(out_root),
        "target_count": int(args.target_count),
        "dry_run": bool(args.dry_run),
        "scenarios": [],
    }

    for problem in problems:
        scenario_summary: Dict[str, Any] = {
            "scenario": problem.problem_id,
            "target_service": problem.target_service,
            "family": problem.task_family or problem.category,
            "existing": [],
            "collected": [],
            "failed": [],
            "attempts": [],
            "status": "",
        }
        existing_audits = [audit_episode(path, problem) for path in episode_paths(problem.problem_id)]
        scenario_summary["existing"] = existing_audits
        ready_count = sum(1 for audit in existing_audits if audit.get("benchmark_ready"))
        scenario_summary["ready_count"] = ready_count

        if ready_count >= args.target_count:
            scenario_summary["status"] = "target_met"
            summary["scenarios"].append(scenario_summary)
            write_summaries(out_root, summary)
            continue

        missing = args.target_count - ready_count
        if args.dry_run:
            scenario_summary["status"] = f"dry_run_missing_{missing}"
            summary["scenarios"].append(scenario_summary)
            write_summaries(out_root, summary)
            continue

        attempts = 0
        while ready_count < args.target_count and attempts < args.max_attempts_per_scenario:
            attempts += 1
            attempt_id = f"{problem.problem_id}_attempt_{attempts:02d}"
            attempt_log_dir = out_root / "bulk_logs"
            before = {path for path in out_root.iterdir() if path.is_dir()}
            probe_cmd = [
                sys.executable,
                "scripts/run_evidence_probe.py",
                str(problem.experiment_file),
                "--out-dir",
                str(out_root),
                "--lookback-minutes",
                str(max(1, args.lookback_minutes)),
            ]
            if args.warm_cluster:
                probe_cmd.append("--warm-cluster")
            if args.include_dependencies or problem.category == "dependency_trace":
                probe_cmd.append("--include-dependencies")

            probe = run(probe_cmd, cwd=ROOT, log_path=attempt_log_dir / f"{attempt_id}_probe.log")
            attempt_record: Dict[str, Any] = {
                "attempt": attempts,
                "probe": {"returncode": probe["returncode"], "log": probe["log"]},
            }
            scenario_summary["attempts"].append(attempt_record)

            try:
                cleanup = cleanup_check(args.namespace)
                attempt_record["cleanup_check"] = cleanup
            except Exception as exc:
                attempt_record["cleanup_check"] = {"ok": False, "error": str(exc)}
                scenario_summary["failed"].append({"attempt": attempts, "reason": f"cleanup check failed: {exc}"})
                scenario_summary["status"] = "blocked_cleanup_failed"
                summary["scenarios"].append(scenario_summary)
                summary["finished_at_utc"] = utc_now()
                write_summaries(out_root, summary)
                return 2

            if probe["returncode"] != 0:
                scenario_summary["failed"].append({"attempt": attempts, "reason": "probe failed", "log": probe["log"]})
                write_summaries(out_root, summary)
                continue

            run_dir = newest_run_dir(out_root, before)
            if run_dir is None:
                scenario_summary["failed"].append({"attempt": attempts, "reason": "probe succeeded but run directory not found"})
                write_summaries(out_root, summary)
                continue
            attempt_record["run_dir"] = str(run_dir)

            capture_cmd = [
                sys.executable,
                "scripts/capture_episode_dataset.py",
                str(run_dir),
                "--benchmark-suite",
                str(suite_path),
                "--problem-id",
                problem.problem_id,
                "--difficulty",
                args.difficulty,
            ]
            capture = run(capture_cmd, cwd=ROOT, log_path=attempt_log_dir / f"{attempt_id}_capture.log")
            attempt_record["capture"] = {"returncode": capture["returncode"], "log": capture["log"]}
            if capture["returncode"] != 0:
                scenario_summary["failed"].append({"attempt": attempts, "reason": "capture failed", "log": capture["log"]})
                write_summaries(out_root, summary)
                continue

            output_lines = [line.strip() for line in capture["stdout"].splitlines() if line.strip()]
            package_path = Path(output_lines[-1]).resolve() if output_lines else None
            if package_path is None or not package_path.exists():
                scenario_summary["failed"].append({"attempt": attempts, "reason": "capture did not print a package path"})
                write_summaries(out_root, summary)
                continue
            audit = audit_episode(package_path, problem)
            attempt_record["package"] = str(package_path)
            attempt_record["audit"] = audit
            if audit.get("benchmark_ready"):
                scenario_summary["collected"].append(audit)
                ready_count += 1
                scenario_summary["ready_count"] = ready_count
            else:
                scenario_summary["failed"].append({"attempt": attempts, "reason": audit.get("reason", "audit failed"), "package": str(package_path)})

            write_summaries(out_root, summary)

        scenario_summary["status"] = "target_met" if ready_count >= args.target_count else f"incomplete_{ready_count}_of_{args.target_count}"
        summary["scenarios"].append(scenario_summary)
        write_summaries(out_root, summary)

    summary["finished_at_utc"] = utc_now()
    write_summaries(out_root, summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
