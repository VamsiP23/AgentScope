from __future__ import annotations

import sys

from agent_graph.actor import Actor
from agent_graph.schemas import Hypothesis
from agent_graph.tools.actions import ActionTools
from agent_graph.tools.kubernetes import KubernetesTools
from detectors.schemas import DetectionConfig

from agent_graph.state import IncidentState


def act_node(state: IncidentState) -> IncidentState:
    config = DetectionConfig(
        namespace=state["namespace"],
        prom_url=state["prom_url"],
        window=state.get("window", "1m"),
        target_deployment=state.get("target_deployment", ""),
        error_ratio_threshold=state.get("error_ratio_threshold", 0.10),
        service_error_rps_threshold=state.get("service_error_rps_threshold", 0.50),
        min_total_rps=state.get("min_total_rps", 0.10),
        restart_count_threshold=state.get("restart_count_threshold", 1),
    )
    actor = Actor(config, ActionTools(), KubernetesTools(), dry_run=state.get("dry_run", True))
    supported = state.get("supported_hypothesis")
    attempted_actions = {item.get("action", "") for item in state.get("attempted_actions", [])}
    attempted_history = state.get("attempted_actions", [])
    action = actor.run(Hypothesis(**supported), attempted_actions, attempted_history) if supported else actor.run(Hypothesis(
        id="no_strong_hypothesis",
        title="No strong hypothesis from detector output",
        suspected_service=state.get("target_deployment", ""),
        category="unknown",
        confidence=0.0,
        rationale="missing supported hypothesis",
        validation_plan=[],
    ), attempted_actions, attempted_history)
    print(
        f"[agent] state=act action={action.action} target={action.target} dry_run={action.dry_run} "
        f"rationale={action.rationale}",
        file=sys.stderr,
        flush=True,
    )
    attempted = [*state.get("attempted_actions", []), action.to_dict()]
    return {
        **state,
        "current_action": action.to_dict(),
        "attempted_actions": attempted,
        "state_history": [*state.get("state_history", []), "act"],
    }
