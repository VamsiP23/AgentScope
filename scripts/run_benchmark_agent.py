#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_graph.aci import AgentCloudInterface
from agent_graph.diagnostic_agent import DiagnosticAgent
from agent_graph.react_agent import ReActAgent
from agent_graph.react_render import summarize_output
from benchmarking.replay import ReplayAgentCloudInterface
from benchmarking.problem import load_benchmark_suite


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def str_to_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"invalid boolean value: {value}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run a benchmark agent against a live or replay backend.")
    p.add_argument("--agent-type", default="react")
    p.add_argument("--backend", default="live", choices=["live", "replay"])
    p.add_argument("--replay-dataset", default="")
    p.add_argument("--namespace", default="default")
    p.add_argument("--prom-url", default="http://localhost:9090")
    p.add_argument("--jaeger-url", default="http://localhost:16686")
    p.add_argument("--target-deployment", default="")
    p.add_argument("--problem-description", default=(
        "An incident has been detected in the Online Boutique cluster. "
        "Investigate using available tools and identify the root cause and appropriate remediation action."
    ))
    p.add_argument("--jaeger-enabled", type=str_to_bool, default=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--provider", default="")
    p.add_argument("--model", default="")
    p.add_argument("--max-steps", type=int, default=35)
    p.add_argument("--seed-detection-file", default="")
    p.add_argument("--out-file", default="")
    p.add_argument("--benchmark-suite", default="")
    p.add_argument("--problem-id", default="")
    p.add_argument("--evidence-view", default="raw", choices=["raw", "compact", "distilled"])
    p.add_argument("--print-json", action="store_true")
    return p


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def summarize_seeded_detection(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not payload:
        return {}

    suspicious_services = []
    for service in payload.get("suspicious_services", []) or []:
        cleaned = str(service).strip()
        if cleaned and cleaned not in suspicious_services:
            suspicious_services.append(cleaned)

    critical_findings = []
    for finding in payload.get("findings", []) or []:
        if not bool((finding or {}).get("triggered", False)):
            continue
        critical_findings.append(
            {
                "name": str((finding or {}).get("name", "")),
                "service": str((finding or {}).get("service", "")),
                "severity": str((finding or {}).get("severity", "")),
                "reason": str((finding or {}).get("reason", "")),
            }
        )

    return {
        "summary": str(payload.get("summary", "")),
        "incident_detected": bool(payload.get("incident_detected", False)),
        "suspicious_services": suspicious_services,
        "critical_findings": critical_findings[:5],
    }


def normalize_text(value: str) -> str:
    return " ".join(str(value).split())


def presentation_error(value: Any) -> str:
    text = normalize_text(value)
    lowered = text.lower()
    if not text:
        return ""
    if "container" in lowered and "waiting to start" in lowered:
        return "pod not started yet (expected during image-pull failure)"
    if "errimagepull" in lowered or "imagepullbackoff" in lowered:
        return "image pull failed for the new rollout pod"
    if "failed to pull image" in lowered:
        return "new rollout pod cannot pull its image"
    return text


def pretty_step_summary(step_record: Dict[str, Any]) -> list[str]:
    output = step_record.get("output", {}) or {}
    summary = summarize_output(output)
    lines = [
        f"step {step_record.get('step')}: {step_record.get('tool_called')} "
        f"(call_id={step_record.get('call_id')})"
    ]
    thought = normalize_text(step_record.get("thought", ""))
    if thought:
        lines.append(f"  reasoning: {thought}")

    highlight_parts = []
    for key in (
        "service",
        "availability_gap",
        "rollout_progressing",
        "startup_failure_markers",
        "metrics_signal",
        "trace_signal",
        "dependency_trace_signal",
        "summary",
        "trace_count",
        "bottleneck_service",
        "exit_code",
        "executed",
    ):
        value = summary.get(key)
        if value in (None, "", [], {}):
            continue
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        if isinstance(value, dict):
            continue
        highlight_parts.append(f"{key}={value}")
    rendered_error = presentation_error(summary.get("error"))
    if rendered_error:
        highlight_parts.append(f"note={rendered_error}")
    if highlight_parts:
        lines.append(f"  result: {' | '.join(highlight_parts[:6])}")

    if step_record.get("tool_called") == "submit_solution":
        root_cause = normalize_text(output.get("root_cause", ""))
        action_taken = normalize_text(output.get("action_taken", ""))
        fault_class = normalize_text(output.get("fault_class", ""))
        affected_service = normalize_text(output.get("affected_service", ""))
        action_type = normalize_text(output.get("action_type", ""))
        confidence = output.get("confidence")
        lines.append("  solution:")
        if fault_class:
            lines.append(f"    fault_class: {fault_class}")
        if affected_service:
            lines.append(f"    affected_service: {affected_service}")
        if root_cause:
            lines.append(f"    root_cause: {root_cause}")
        if action_type:
            lines.append(f"    action_type: {action_type}")
        if action_taken:
            lines.append(f"    action_taken: {action_taken}")
        if confidence not in (None, ""):
            lines.append(f"    confidence: {confidence}")
    return lines


def main() -> int:
    args = build_parser().parse_args()
    out_path = Path(args.out_file) if args.out_file else Path("benchmark_agent_report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    aci_log_path = out_path.with_name("aci_run_log.jsonl")

    if args.backend == "replay":
        if not args.replay_dataset:
            raise RuntimeError("--replay-dataset is required when --backend=replay")
        aci = ReplayAgentCloudInterface(
            args.replay_dataset,
            run_log_path=str(aci_log_path),
            evidence_view=args.evidence_view,
        )
        initial_context = dict(aci.dataset.initial_context)
        seeded_detection = {}
    else:
        aci = AgentCloudInterface(
            namespace=args.namespace,
            prom_url=args.prom_url,
            jaeger_url=args.jaeger_url,
            run_log_path=str(aci_log_path),
            jaeger_enabled=bool(args.jaeger_enabled),
            dry_run=bool(args.dry_run),
            evidence_view=args.evidence_view,
        )
        seeded_detection = read_json(Path(args.seed_detection_file)) if args.seed_detection_file else {}
        initial_context = summarize_seeded_detection(seeded_detection)

    agent_type = args.agent_type.strip().lower()
    if agent_type not in {"react", "bounded_react", "diagnostic"}:
        raise RuntimeError(f"unsupported agent type: {args.agent_type}")

    problem = {}
    if args.benchmark_suite and args.problem_id:
        suite = load_benchmark_suite(Path(args.benchmark_suite))
        problem_spec = suite.find_problem_by_id(args.problem_id)
        if problem_spec is not None:
            problem = problem_spec.to_dict()

    def build_payload(result: Dict[str, Any], error: str = "") -> Dict[str, Any]:
        return {
            "agent_type": "benchmark",
            "timestamp_utc": utc_now(),
            "namespace": args.namespace,
            "prom_url": args.prom_url,
            "jaeger_url": args.jaeger_url,
            "target_deployment": args.target_deployment,
            "problem_description": args.problem_description,
            "jaeger_enabled": bool(args.jaeger_enabled),
            "dry_run": bool(args.dry_run),
            "provider": result.get("provider", args.provider or ""),
            "model": result.get("model", args.model or ""),
            "agent_variant": result.get("agent_variant", args.agent_type),
            "backend": args.backend,
            "diagnosis_only": args.backend == "replay",
            "replay_dataset": args.replay_dataset,
            "problem": problem,
            "evidence_view": args.evidence_view,
            "seeded_detection": seeded_detection,
            "guardrail_events": result.get("guardrail_events", getattr(agent, "guardrail_events", [])),
            "diagnostic_events": result.get("diagnostic_events", []),
            "evidence_ledger": result.get("evidence_ledger", {}),
            "steps": result.get("steps", []),
            "solution": result.get("solution", {}),
            "verification": {},
            "aci_run_log": str(aci_log_path),
            "error": error or None,
        }

    def emit_step(step_record: Dict[str, Any]) -> None:
        for line in pretty_step_summary(step_record):
            print(line, flush=True)
        partial = build_payload(
            {
                "provider": getattr(agent, "provider", args.provider or ""),
                "model": getattr(agent, "model", args.model or ""),
                "agent_variant": getattr(agent, "agent_variant", args.agent_type),
                "guardrail_events": getattr(agent, "guardrail_events", []),
                "diagnostic_events": getattr(agent, "llm_events", []),
                "evidence_ledger": getattr(getattr(agent, "ledger", None), "snapshot", lambda: {})(),
                "steps": list(getattr(agent, "trace", getattr(agent, "steps", []))),
                "solution": getattr(aci, "submitted_solution", {}) or {},
            }
        )
        out_path.write_text(json.dumps(partial, indent=2))

    if agent_type == "diagnostic":
        agent = DiagnosticAgent(
            aci=aci,
            provider=args.provider or None,
            model=args.model or None,
            max_steps=args.max_steps,
            diagnosis_only=args.backend == "replay",
            step_callback=emit_step,
        )
    else:
        agent = ReActAgent(
            aci=aci,  # type: ignore[arg-type]
            provider=args.provider or None,
            model=args.model or None,
            max_steps=args.max_steps,
            allow_exec_shell=not bool(args.dry_run),
            diagnosis_only=args.backend == "replay",
            agent_variant="bounded_react" if agent_type == "bounded_react" else "pure_react",
            step_callback=emit_step,
        )

    try:
        result = agent.run(args.problem_description, initial_context=initial_context)
    except Exception as exc:
        payload = build_payload(
            {
                "provider": getattr(agent, "provider", args.provider or ""),
                "model": getattr(agent, "model", args.model or ""),
                "agent_variant": getattr(agent, "agent_variant", args.agent_type),
                "guardrail_events": getattr(agent, "guardrail_events", []),
                "diagnostic_events": getattr(agent, "llm_events", []),
                "evidence_ledger": getattr(getattr(agent, "ledger", None), "snapshot", lambda: {})(),
                "steps": list(getattr(agent, "trace", getattr(agent, "steps", []))),
                "solution": getattr(aci, "submitted_solution", {}) or {},
            },
            error=str(exc),
        )
        out_path.write_text(json.dumps(payload, indent=2))
        if args.print_json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"agent failed: {exc}", flush=True)
        raise

    payload = build_payload(result)
    out_path.write_text(json.dumps(payload, indent=2))
    if args.print_json:
        print(json.dumps(payload, indent=2))
    else:
        solution = payload.get("solution", {}) or {}
        print(
            "complete: "
            f"provider={payload.get('provider')} model={payload.get('model')} "
            f"fault_class={solution.get('fault_class', '')} "
            f"service={solution.get('affected_service', '')} "
            f"action={solution.get('action_type', '')}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
