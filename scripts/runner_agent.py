from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List

from benchmarking.problem import ProblemSpec
from runner_common import (
    ROOT,
    bool_value,
    int_value,
    print_status,
    read_detection_report,
    rel_path,
    require_binary,
    str_value,
    utc_now,
)


def build_monitor_cmd(namespace: str, detector: Dict[str, Any], run_dir: Path) -> List[str]:
    primary_detectors = detector.get("primary_detectors", [
        "error_ratio",
        "service_error_rate",
        "service_latency",
        "deployment_availability",
        "service_endpoints",
        "service_port_alignment",
        "native_stress_job",
    ])
    if isinstance(primary_detectors, str):
        primary_detectors = [item.strip() for item in primary_detectors.split(",") if item.strip()]
    if not isinstance(primary_detectors, list):
        primary_detectors = [
            "error_ratio",
            "service_error_rate",
            "service_latency",
            "deployment_availability",
            "service_endpoints",
            "service_port_alignment",
            "native_stress_job",
        ]
    return [
        "./scripts/monitor_loop.py",
        "--namespace",
        namespace,
        "--prom-url",
        str_value(detector.get("prom_url"), "http://localhost:9090"),
        "--window",
        str_value(detector.get("window"), "1m"),
        "--target-deployment",
        str_value(detector.get("target_deployment"), ""),
        "--error-ratio-threshold",
        str(detector.get("error_ratio_threshold", 0.10)),
        "--service-error-rps-threshold",
        str(detector.get("service_error_rps_threshold", 0.50)),
        "--service-latency-threshold-ms",
        str(detector.get("service_latency_threshold_ms", 1000.0)),
        "--latency-consecutive-required",
        str(int_value(detector.get("latency_consecutive_required"), 2)),
        "--service-error-consecutive-required",
        str(int_value(detector.get("service_error_consecutive_required"), 1)),
        "--min-total-rps",
        str(detector.get("min_total_rps", 0.10)),
        "--restart-count-threshold",
        str(int_value(detector.get("restart_count_threshold"), 1)),
        "--primary-detectors",
        ",".join(str(item) for item in primary_detectors),
        "--out-dir",
        str(run_dir / "detector_runs"),
        "--interval-seconds",
        str(int_value(detector.get("interval_seconds"), 10)),
    ]


def build_agent_cmd(
    namespace: str,
    detector: Dict[str, Any],
    agent: Dict[str, Any],
    run_dir: Path,
    seeded_detection_path: Path | None = None,
    benchmark_suite_path: Path | None = None,
    problem: ProblemSpec | None = None,
) -> List[str]:
    agent_type = str_value(agent.get("type"), "pipeline").strip().lower()
    if agent_type not in {"react", "bounded_react", "diagnostic"}:
        raise RuntimeError(
            f"unsupported agent type '{agent_type}'. Use type=react, type=bounded_react, or type=diagnostic."
        )

    cmd = [
        "python3",
        "./scripts/run_benchmark_agent.py",
        "--agent-type",
        agent_type,
        "--backend",
        "live",
        "--namespace",
        namespace,
        "--prom-url",
        str_value(detector.get("prom_url"), "http://localhost:9090"),
        "--jaeger-url",
        str_value(agent.get("jaeger_url"), "http://localhost:16686"),
        "--target-deployment",
        str_value(agent.get("target_deployment"), str_value(detector.get("target_deployment"), "")),
        "--problem-description",
        str_value(
            agent.get("problem_description"),
            (
                "An incident has been detected in the Online Boutique cluster. "
                "Investigate using available tools and identify the root cause and appropriate remediation action."
            ),
        ),
        "--jaeger-enabled",
        "true" if bool_value(agent.get("jaeger_enabled"), True) else "false",
        "--max-steps",
        str(int_value(agent.get("max_steps"), 35)),
        "--seed-detection-file",
        str(seeded_detection_path) if seeded_detection_path is not None else "",
        "--out-file",
        str(run_dir / "agent_report.json"),
    ]
    provider = str_value(agent.get("provider"), "")
    model = str_value(agent.get("model"), "")
    if provider:
        cmd.extend(["--provider", provider])
    if model:
        cmd.extend(["--model", model])
    if bool_value(agent.get("dry_run"), True):
        cmd.append("--dry-run")
    if benchmark_suite_path is not None and problem is not None:
        cmd.extend(["--benchmark-suite", str(benchmark_suite_path), "--problem-id", problem.problem_id])
    return cmd


def ensure_ollama_model_available() -> None:
    provider = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if provider != "ollama":
        return

    require_binary("ollama")
    model = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b").strip()
    if not model:
        raise RuntimeError("OLLAMA_MODEL must be set when LLM_PROVIDER=ollama")

    show_proc = subprocess.run(["ollama", "show", model], cwd=ROOT, capture_output=True, text=True, check=False)
    if show_proc.returncode == 0:
        print_status(f"phase=agent: ollama model ready ({model})")
        return

    print_status(f"phase=agent: pulling missing ollama model ({model})")
    pull_proc = subprocess.run(["ollama", "pull", model], cwd=ROOT, capture_output=True, text=True, check=False)
    if pull_proc.returncode != 0:
        raise RuntimeError(
            "failed to pull ollama model "
            f"{model}: {pull_proc.stderr.strip() or pull_proc.stdout.strip() or 'unknown error'}"
        )
    print_status(f"phase=agent: ollama model pulled ({model})")


def prewarm_agent_runtime(agent_cfg: Dict[str, Any]) -> None:
    if not bool_value(agent_cfg.get("enabled"), False):
        return

    provider = str_value(agent_cfg.get("provider"), os.environ.get("LLM_PROVIDER", "")).strip().lower()
    if provider == "claude":
        provider = "anthropic"
    if provider != "ollama":
        return

    ensure_ollama_model_available()
    model = str_value(agent_cfg.get("model"), os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")).strip()
    if not model:
        raise RuntimeError("OLLAMA_MODEL must be set when warming Ollama")

    from agent_graph.reasoning.llm import ResponsesJSONClient

    print_status(f"phase=agent_prewarm: warming ollama model ({model})")
    client = ResponsesJSONClient(model=model, provider="ollama")
    client.complete_json(
        name="warmup",
        schema={
            "type": "object",
            "properties": {"ready": {"type": "boolean"}},
            "required": ["ready"],
            "additionalProperties": False,
        },
        prompt={"task": "Warm the local model runtime.", "instruction": "Return {'ready': true}."},
    )
    print_status(f"phase=agent_prewarm: completed ({model})")


def wait_for_incident(detector_runs_dir: Path, max_wait_seconds: int, poll_interval: int) -> Dict[str, Any]:
    latest_path = detector_runs_dir / "latest_detection.json"
    deadline = time.time() + max_wait_seconds
    last_summary = ""
    while time.time() <= deadline:
        report = read_detection_report(latest_path)
        if report:
            summary = str(report.get("summary", ""))
            if summary and summary != last_summary:
                print_status(f"phase=agent_wait: detector summary='{summary}'")
                last_summary = summary
            if report.get("incident_detected", False):
                return report
        time.sleep(max(1, poll_interval))
    return read_detection_report(latest_path)


def validate_telemetry_sources(
    namespace: str,
    prom_url: str,
    jaeger_url: str,
    run_dir: Path,
    required_services: List[str],
    wait_seconds: int = 45,
    poll_seconds: int = 5,
) -> Dict[str, Any]:
    started = utc_now()
    cmd = [
        "python3",
        "./scripts/validate_telemetry.py",
        "--prom-url",
        prom_url,
        "--jaeger-url",
        jaeger_url,
        "--namespace",
        namespace,
        "--require-services",
        ",".join(required_services),
        "--wait-seconds",
        str(wait_seconds),
        "--poll-seconds",
        str(poll_seconds),
    ]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    log_path = run_dir / "telemetry_validation.log"
    log_path.write_text(
        "COMMAND: " + " ".join(shlex.quote(part) for part in cmd) + "\n\n"
        + "STDOUT:\n"
        + proc.stdout
        + "\nSTDERR:\n"
        + proc.stderr
    )
    payload: Dict[str, Any] = {}
    stdout = (proc.stdout or "").strip()
    if stdout:
        try:
            payload = json.loads(stdout)
        except Exception:
            payload = {}
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "started_at_utc": started,
        "finished_at_utc": utc_now(),
        "log": rel_path(log_path),
        "report": payload if isinstance(payload, dict) else {},
    }
