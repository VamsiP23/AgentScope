from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class IncidentState(TypedDict, total=False):
    incident_id: str
    namespace: str
    prom_url: str
    jaeger_url: str
    target_deployment: str
    window: str
    mode: str
    dry_run: bool
    max_iterations: int
    research_max_tool_calls: int
    verify_wait_seconds: int
    error_ratio_threshold: float
    service_error_rps_threshold: float
    service_latency_threshold_ms: float
    min_total_rps: float
    restart_count_threshold: int

    detection: Dict[str, Any]
    topology_context: Dict[str, Any]
    hypotheses: List[Dict[str, Any]]
    evidence: List[Dict[str, Any]]
    research_trace: List[Dict[str, Any]]
    research_mode: str
    supported_hypothesis: Optional[Dict[str, Any]]
    policy_decision: Optional[Dict[str, Any]]

    attempted_actions: List[Dict[str, Any]]
    current_action: Optional[Dict[str, Any]]
    verification: Optional[Dict[str, Any]]
    verifier_evidence: Optional[Dict[str, Any]]

    iteration: int
    final_state: Optional[str]
    summary: Optional[str]
    state_history: List[str]
