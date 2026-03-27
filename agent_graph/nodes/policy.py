from __future__ import annotations

import sys

from agent_graph.policy import Policy
from agent_graph.schemas import EvidenceItem, Hypothesis
from agent_graph.state import IncidentState


def policy_node(state: IncidentState) -> IncidentState:
    policy = Policy(mode=state.get("mode", "heuristic"))
    hypotheses = [Hypothesis(**item) for item in state.get("hypotheses", [])]
    evidence = [EvidenceItem(**item) for item in state.get("evidence", [])]
    decision = policy.run(hypotheses, evidence)
    print(
        f"[agent] state=policy supported={decision.supported_hypothesis_id or 'none'} "
        f"actionability={decision.actionability} confidence={decision.confidence:.2f}",
        file=sys.stderr,
        flush=True,
    )
    return {
        **state,
        "supported_hypothesis": decision.supported_hypothesis or None,
        "policy_decision": decision.to_dict(),
        "state_history": [*state.get("state_history", []), "policy"],
    }
