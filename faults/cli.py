from __future__ import annotations

import argparse
import sys
import time

from .common import FaultContext, require_kubectl
from .scenarios import SCENARIOS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inject and revert deterministic failure scenarios for Online Boutique."
    )
    parser.add_argument("action", choices=["apply", "revert"])
    parser.add_argument("scenario", choices=sorted(SCENARIOS.keys()))
    parser.add_argument("-n", "--namespace", default="default")
    parser.add_argument("-d", "--duration", type=int, default=0)
    parser.add_argument("-t", "--target", default="")
    parser.add_argument("-l", "--latency", default="3s")
    parser.add_argument("-r", "--replicas", type=int, default=1)
    parser.add_argument("--cpu-limit", default="100m")
    parser.add_argument("--cpu-request", default="50m")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    require_kubectl()

    if args.duration < 0:
        print("Duration must be a non-negative integer.", file=sys.stderr)
        return 1

    scenario = SCENARIOS[args.scenario]
    ctx = FaultContext(
        namespace=args.namespace,
        target=args.target,
        latency=args.latency,
        replicas=args.replicas,
        cpu_limit=args.cpu_limit,
        cpu_request=args.cpu_request,
    )

    try:
        if args.action == "apply":
            print(scenario.apply(ctx))
            if args.duration > 0:
                print(f"Holding scenario '{args.scenario}' for {args.duration}s...")
                time.sleep(args.duration)
                print(scenario.revert(ctx))
                print(f"Auto-reverted scenario '{args.scenario}'.")
            else:
                suffix = f" -t {args.target}" if args.target else ""
                print(f"Scenario '{args.scenario}' applied. Revert with:")
                print(f"  ./scripts/failure_inject.sh revert {args.scenario} -n {args.namespace}{suffix}")
        else:
            print(scenario.revert(ctx))
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
