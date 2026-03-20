from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class IncidentState(TypedDict, total=False):
    incident_id: str
    namespace: str
    prom_url: str
    jaeger_url: str
    target_deployment: str
    mode: str
    dry_run: bool
    max_iterations: int
    verify_wait_seconds: int

    detection: Dict[str, Any]
    topology_context: Dict[str, Any]
    hypotheses: List[Dict[str, Any]]
    evidence: List[Dict[str, Any]]
    supported_hypothesis: Optional[Dict[str, Any]]

    attempted_actions: List[Dict[str, Any]]
    current_action: Optional[Dict[str, Any]]
    verification: Optional[Dict[str, Any]]

    iteration: int
    final_state: Optional[str]
    summary: Optional[str]
    state_history: List[str]
