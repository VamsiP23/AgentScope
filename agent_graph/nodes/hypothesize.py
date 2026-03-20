from __future__ import annotations

import sys

from agent_graph.hypothesizer import Hypothesizer

from agent_graph.state import IncidentState


def hypothesize_node(state: IncidentState) -> IncidentState:
    model = Hypothesizer(state.get("mode", "heuristic"))
    hypotheses = model.run(state["detection"], state.get("target_deployment", ""))
    print(
        f"[agent] state=hypothesize generated_hypotheses={len(hypotheses)} mode={state.get('mode', 'heuristic')}",
        file=sys.stderr,
        flush=True,
    )
    for idx, item in enumerate(hypotheses, start=1):
        print(
            f"[agent] hypothesis[{idx}] id={item.id} service={item.suspected_service} "
            f"confidence={item.confidence:.2f} rationale={item.rationale}",
            file=sys.stderr,
            flush=True,
        )
    return {
        **state,
        "hypotheses": [item.to_dict() for item in hypotheses],
        "state_history": [*state.get("state_history", []), "hypothesize"],
    }
