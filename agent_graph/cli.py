from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_graph.workflow import build_workflow


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run the LangGraph incident response agent.")
    p.add_argument("--namespace", default="default")
    p.add_argument("--prom-url", default="http://localhost:9090")
    p.add_argument("--jaeger-url", default="http://localhost:16686")
    p.add_argument("--window", default="1m")
    p.add_argument("--target-deployment", default="")
    p.add_argument("--error-ratio-threshold", type=float, default=0.10)
    p.add_argument("--service-error-rps-threshold", type=float, default=0.50)
    p.add_argument("--min-total-rps", type=float, default=0.10)
    p.add_argument("--restart-count-threshold", type=int, default=1)
    p.add_argument("--mode", choices=["heuristic", "llm"], default="heuristic")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--max-iterations", type=int, default=2)
    p.add_argument("--verify-wait-seconds", type=int, default=30)
    p.add_argument("--out-file", default="")
    return p


def main() -> int:
    args = build_parser().parse_args()
    app = build_workflow()
    initial_state = {
        "namespace": args.namespace,
        "prom_url": args.prom_url,
        "jaeger_url": args.jaeger_url,
        "window": args.window,
        "target_deployment": args.target_deployment,
        "error_ratio_threshold": args.error_ratio_threshold,
        "service_error_rps_threshold": args.service_error_rps_threshold,
        "min_total_rps": args.min_total_rps,
        "restart_count_threshold": args.restart_count_threshold,
        "mode": args.mode,
        "dry_run": args.dry_run,
        "max_iterations": args.max_iterations,
        "verify_wait_seconds": args.verify_wait_seconds,
        "iteration": 0,
        "attempted_actions": [],
        "state_history": [],
    }
    result = app.invoke(initial_state)
    payload = json.dumps(result, indent=2)
    if args.out_file:
        path = Path(args.out_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload)
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
