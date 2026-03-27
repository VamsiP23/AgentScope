from __future__ import annotations

import sys

from agent_graph.schemas import ActionPlan
from agent_graph.verifier import Verifier
from detectors.schemas import DetectionConfig

from agent_graph.state import IncidentState


def verify_node(state: IncidentState) -> IncidentState:
    config = DetectionConfig(
        namespace=state["namespace"],
        prom_url=state["prom_url"],
        window=state.get("window", "1m"),
        target_deployment=state.get("target_deployment", ""),
        error_ratio_threshold=state.get("error_ratio_threshold", 0.10),
        service_error_rps_threshold=state.get("service_error_rps_threshold", 0.50),
        service_latency_threshold_ms=state.get("service_latency_threshold_ms", 1000.0),
        min_total_rps=state.get("min_total_rps", 0.10),
        restart_count_threshold=state.get("restart_count_threshold", 1),
    )
    verifier = Verifier(
        config,
        jaeger_url=state["jaeger_url"],
        mode=state.get("mode", "heuristic"),
        wait_seconds=state.get("verify_wait_seconds", 30),
    )
    action = ActionPlan(**state["current_action"])
    verification = verifier.run(action, state["detection"])
    stages = verification.stages or {}
    print(
        f"[agent] state=verify recovered={verification.recovered} "
        f"root_cause_mitigated={verification.root_cause_mitigated} "
        f"before='{verification.before_summary}' after='{verification.after_summary}' "
        f"stages={stages}",
        file=sys.stderr,
        flush=True,
    )
    return {
        **state,
        "verification": verification.to_dict(),
        "verifier_evidence": verification.evidence,
        "iteration": state.get("iteration", 0) + 1,
        "state_history": [*state.get("state_history", []), "verify"],
    }
