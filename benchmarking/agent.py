from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Protocol


@dataclass
class AgentRunContext:
    namespace: str = "default"
    prom_url: str = "http://localhost:9090"
    jaeger_url: str = "http://localhost:16686"
    target_deployment: str = ""
    problem_description: str = ""
    benchmark_suite: str = ""
    problem_id: str = ""
    seeded_detection: Dict[str, Any] = field(default_factory=dict)
    initial_context: Dict[str, Any] = field(default_factory=dict)
    dry_run: bool = True
    provider: str = ""
    model: str = ""
    max_steps: int = 35
    out_file: str = ""
    backend: str = "live"
    replay_dataset: str = ""


class BenchmarkAgent(Protocol):
    agent_variant: str

    def run(self, problem_description: str, initial_context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        ...


@dataclass
class BenchmarkAgentResult:
    agent_type: str
    agent_variant: str
    provider: str
    model: str
    steps: List[Dict[str, Any]]
    solution: Dict[str, Any]
    guardrail_events: List[Dict[str, Any]] = field(default_factory=list)
    verification: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_type": self.agent_type,
            "agent_variant": self.agent_variant,
            "provider": self.provider,
            "model": self.model,
            "steps": list(self.steps),
            "solution": dict(self.solution),
            "guardrail_events": list(self.guardrail_events),
            "verification": dict(self.verification),
        }


def default_report_path(root: Path, problem_id: str, agent_variant: str) -> Path:
    suffix = f"{problem_id or 'adhoc'}_{agent_variant}.json"
    return root / "results" / "benchmark_agents" / suffix
