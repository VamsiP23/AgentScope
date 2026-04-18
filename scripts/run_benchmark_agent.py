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
from agent_graph.react_agent import ReActAgent
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

    if args.agent_type.strip().lower() != "react":
        raise RuntimeError(f"unsupported agent type: {args.agent_type}")

    problem = {}
    if args.benchmark_suite and args.problem_id:
        suite = load_benchmark_suite(Path(args.benchmark_suite))
        problem_spec = suite.find_problem_by_id(args.problem_id)
        if problem_spec is not None:
            problem = problem_spec.to_dict()

    agent = ReActAgent(
        aci=aci,  # type: ignore[arg-type]
        provider=args.provider or None,
        model=args.model or None,
        max_steps=args.max_steps,
        allow_exec_shell=not bool(args.dry_run),
        diagnosis_only=args.backend == "replay",
        step_callback=None,
    )

    result = agent.run(args.problem_description, initial_context=initial_context)
    payload = {
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
        "steps": result.get("steps", []),
        "solution": result.get("solution", {}),
        "verification": {},
        "aci_run_log": str(aci_log_path),
        "error": None,
    }
    out_path.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
