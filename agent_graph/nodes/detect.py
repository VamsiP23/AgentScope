from __future__ import annotations

import sys
from typing import Any

from agent_graph.knowledge.topology import service_context
from detectors.monitor import build_report
from detectors.schemas import DetectionConfig
from detectors.utils import utc_now

from agent_graph.state import IncidentState


def detect_node(state: IncidentState) -> IncidentState:
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
    detection = build_report(config).to_dict()
    print(
        f"[agent] state=detect incident_detected={detection.get('incident_detected', False)} "
        f"summary={detection.get('summary', '')}",
        file=sys.stderr,
        flush=True,
    )
    target = state.get("target_deployment", "")
    topology_context = {target: service_context(target)} if target else {}
    return {
        **state,
        "incident_id": state.get("incident_id", utc_now()),
        "detection": detection,
        "topology_context": topology_context,
        "state_history": [*state.get("state_history", []), "detect"],
    }
