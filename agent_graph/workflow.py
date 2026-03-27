from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from agent_graph.nodes.act import act_node
from agent_graph.nodes.detect import detect_node
from agent_graph.nodes.hypothesize import hypothesize_node
from agent_graph.nodes.policy import policy_node
from agent_graph.nodes.research import research_node
from agent_graph.nodes.verify import verify_node
from agent_graph.state import IncidentState


def build_workflow() -> Any:
    graph = StateGraph(IncidentState)
    graph.add_node("detect", detect_node)
    graph.add_node("hypothesize", hypothesize_node)
    graph.add_node("research", research_node)
    graph.add_node("policy", policy_node)
    graph.add_node("act", act_node)
    graph.add_node("verify", verify_node)

    graph.set_entry_point("detect")

    def route_after_detect(state: IncidentState) -> str:
        if not state.get("detection", {}).get("incident_detected", False):
            return END
        return "hypothesize"

    def route_after_verify(state: IncidentState) -> str:
        verification = state.get("verification") or {}
        if verification.get("recovered", False):
            return END
        if verification.get("root_cause_mitigated", False):
            return END
        if state.get("iteration", 0) >= state.get("max_iterations", 2):
            return END
        return "hypothesize"

    graph.add_conditional_edges("detect", route_after_detect, {"hypothesize": "hypothesize", END: END})
    graph.add_edge("hypothesize", "research")
    graph.add_edge("research", "policy")
    graph.add_edge("policy", "act")
    graph.add_edge("act", "verify")
    graph.add_conditional_edges("verify", route_after_verify, {"hypothesize": "hypothesize", END: END})
    return graph.compile()
