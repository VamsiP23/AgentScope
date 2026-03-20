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
        min_total_rps=state.get("min_total_rps", 0.10),
        restart_count_threshold=state.get("restart_count_threshold", 1),
    )
    prom = PrometheusTools(state["prom_url"])
    k8s = KubernetesTools()
    jaeger = JaegerTools(state["jaeger_url"])
    researcher = Researcher(config, prom, k8s, jaeger)
    hypotheses = [Hypothesis(**item) for item in state.get("hypotheses", [])]
    evidence = researcher.run(hypotheses)
    supported = researcher.select_supported_hypothesis(hypotheses, evidence) if hypotheses else None
    print(
        f"[agent] state=research evidence_items={len(evidence)} "
        f"supported_hypothesis={(supported.id if supported else 'none')}",
        file=sys.stderr,
        flush=True,
    )
    if supported is not None:
        print(
            f"[agent] supported_hypothesis id={supported.id} service={supported.suspected_service} "
            f"confidence={supported.confidence:.2f} rationale={supported.rationale}",
            file=sys.stderr,
            flush=True,
        )
    return {
        **state,
        "evidence": [item.to_dict() for item in evidence],
        "supported_hypothesis": supported.to_dict() if supported else None,
        "state_history": [*state.get("state_history", []), "research"],
    }
