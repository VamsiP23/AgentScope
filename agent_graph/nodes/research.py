from __future__ import annotations

import sys

from agent_graph.researcher import Researcher
from agent_graph.schemas import Hypothesis
from agent_graph.tools.jaeger import JaegerTools
from agent_graph.tools.kubernetes import KubernetesTools
from agent_graph.tools.prometheus import PrometheusTools
from detectors.schemas import DetectionConfig

from agent_graph.state import IncidentState


def research_node(state: IncidentState) -> IncidentState:
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
    prom = PrometheusTools(state["prom_url"])
    k8s = KubernetesTools()
    jaeger = JaegerTools(state["jaeger_url"])
    researcher = Researcher(config, prom, k8s, jaeger, mode=state.get("mode", "heuristic"))
    hypotheses = [Hypothesis(**item) for item in state.get("hypotheses", [])]
    evidence, research_trace, research_mode = researcher.run(
        hypotheses,
        max_tool_calls=int(state.get("research_max_tool_calls", 5)),
    )
    print(
        f"[agent] state=research evidence_items={len(evidence)} "
        f"tool_calls={len(research_trace)} mode={research_mode}",
        file=sys.stderr,
        flush=True,
    )
    return {
        **state,
        "evidence": [item.to_dict() for item in evidence],
        "research_trace": [item.to_dict() for item in research_trace],
        "research_mode": research_mode,
        "state_history": [*state.get("state_history", []), "research"],
    }
