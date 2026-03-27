from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from agent_graph.reasoning.llm import ResponsesJSONClient
from agent_graph.schemas import ActionPlan, EvidenceItem, Hypothesis, PolicyDecision
from agent_graph.tools.actions import ActionTools
from agent_graph.tools.kubernetes import KubernetesTools
from detectors.schemas import DetectionConfig


class Actor:
    def __init__(self, config: DetectionConfig, actions: ActionTools, k8s: KubernetesTools, dry_run: bool = True, mode: str = "heuristic") -> None:
        self.config = config
        self.actions = actions
        self.k8s = k8s
        self.dry_run = dry_run
        self.mode = mode
        self.llm = ResponsesJSONClient()

    def run(
        self,
        hypothesis: Hypothesis,
        policy: PolicyDecision,
        evidence: List[EvidenceItem],
        attempted_actions: Set[str],
        attempted_action_history: List[Dict[str, Any]] | None = None,
    ) -> ActionPlan:
        attempted_action_history = attempted_action_history or []
        if self.mode == "llm":
            if not self.llm.available():
                raise RuntimeError("LLM mode requested but OPENAI_API_KEY is not set")
            try:
                action = self._run_llm(hypothesis, policy, evidence, attempted_actions)
                if action is not None:
                    return action
            except Exception as exc:
                raise RuntimeError(f"LLM actor failed: {exc}") from exc
        return self._run_heuristic(hypothesis, policy, evidence, attempted_actions, attempted_action_history)

    def _run_heuristic(
        self,
        hypothesis: Hypothesis,
        policy: PolicyDecision,
        evidence: List[EvidenceItem],
        attempted_actions: Set[str],
        attempted_action_history: List[Dict[str, Any]],
    ) -> ActionPlan:
        target = hypothesis.suspected_service or self.config.target_deployment
        if policy.actionability != "act":
            return self._wait_action(target, "Policy does not support immediate intervention; gather another observation window.")

        if hypothesis.id == "deployment_unavailable":
            dep = self.k8s.deployment_health(self.config.namespace, target)
            pod_status = self.k8s.deployment_pod_status(self.config.namespace, target)
            desired = int(dep.get("desired", 0))
            if desired == 0 and "restore_replicas" not in attempted_actions:
                return self._scaled_action("restore_replicas", target, 1, "Deployment is scaled to zero; restore replicas first.")
            rollout_progressing = bool(pod_status.get("pod_count", 0)) and (
                bool(dep.get("available", 0))
                or bool(pod_status.get("progressing", False))
                or bool(pod_status.get("ready_pod_count", 0))
            )
            if desired >= 1 and rollout_progressing:
                return self._wait_action(
                    target,
                    "Pods already exist and rollout is progressing; prefer observation before restarting the whole deployment.",
                )
            if "rollout_restart" not in attempted_actions:
                return self._restart_action(target, "Deployment wants replicas but availability is still low.")

        if hypothesis.id == "performance_degradation" and target and "scale_replicas" not in attempted_actions:
            dep = self.k8s.deployment_health(self.config.namespace, target)
            desired = max(1, int(dep.get("desired", 1)))
            return self._scaled_action("scale_replicas", target, desired + 1, "Performance degradation is consistent with capacity loss; scale horizontally.")

        if hypothesis.id in {"dependency_outage", "frontend_symptom_from_downstream_failure"}:
            dependency_target = self.config.target_deployment or target
            if dependency_target and "rollout_restart" not in attempted_actions:
                return self._restart_action(
                    dependency_target,
                    "Frontend symptoms and downstream evidence point at the target dependency rather than the frontend itself.",
                )

        return self._wait_action(target, "No new low-blast-radius action is justified by the current evidence.")

    def _run_llm(
        self,
        hypothesis: Hypothesis,
        policy: PolicyDecision,
        evidence: List[EvidenceItem],
        attempted_actions: Set[str],
    ) -> Optional[ActionPlan]:
        target = hypothesis.suspected_service or self.config.target_deployment
        dep = self.k8s.deployment_health(self.config.namespace, target) if target else {}
        prompt = {
            "task": "Select one safe remediation action for the incident.",
            "hypothesis": hypothesis.to_dict(),
            "policy": policy.to_dict(),
            "evidence": [item.to_dict() for item in evidence],
            "deployment_health": dep,
            "attempted_actions": sorted(attempted_actions),
            "allowed_actions": [
                "wait_and_recheck",
                "restore_replicas",
                "scale_replicas",
                "rollout_restart",
            ],
            "requirements": {
                "prefer lowest blast radius first": True,
                "avoid repeating failed actions": True,
            },
        }
        parsed = self.llm.complete_json(
            name="actor_decision",
            schema={
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "target": {"type": "string"},
                    "replicas": {"type": "integer"},
                    "rationale": {"type": "string"},
                    "expected_signal": {"type": "string"},
                },
                "required": ["action", "target", "replicas", "rationale", "expected_signal"],
                "additionalProperties": False,
            },
            prompt=prompt,
        )
        action = str(parsed.get("action", "wait_and_recheck"))
        selected_target = str(parsed.get("target", target))
        replicas = int(parsed.get("replicas", 0))
        rationale = str(parsed.get("rationale", ""))
        expected_signal = str(parsed.get("expected_signal", ""))
        if action == "restore_replicas":
            return self._scaled_action("restore_replicas", selected_target, max(1, replicas or 1), rationale, expected_signal)
        if action == "scale_replicas":
            return self._scaled_action("scale_replicas", selected_target, max(1, replicas or 2), rationale, expected_signal)
        if action == "rollout_restart":
            return self._restart_action(selected_target, rationale, expected_signal)
        return self._wait_action(selected_target, rationale or "LLM recommended observation before further action.", expected_signal)

    def _scaled_action(self, action_name: str, target: str, replicas: int, rationale: str, expected_signal: str = "") -> ActionPlan:
        result = self.actions.scale_replicas(self.config.namespace, target, replicas=replicas, dry_run=self.dry_run)
        return ActionPlan(
            action=action_name,
            target=target,
            rationale=rationale,
            expected_signal=expected_signal or "Desired and available replicas should increase; error rate should decline.",
            command=result["command"],
            dry_run=self.dry_run,
            executed=bool(result["executed"]),
            result=str(result["result"]),
        )

    def _restart_action(self, target: str, rationale: str, expected_signal: str = "") -> ActionPlan:
        result = self.actions.rollout_restart(self.config.namespace, target, dry_run=self.dry_run)
        return ActionPlan(
            action="rollout_restart",
            target=target,
            rationale=rationale,
            expected_signal=expected_signal or "Pods should roll and availability should recover.",
            command=result["command"],
            dry_run=self.dry_run,
            executed=bool(result["executed"]),
            result=str(result["result"]),
        )

    def _wait_action(self, target: str, rationale: str, expected_signal: str = "") -> ActionPlan:
        result = self.actions.wait_and_recheck(30)
        return ActionPlan(
            action="wait_and_recheck",
            target=target,
            rationale=rationale,
            expected_signal=expected_signal or "Error ratio should stabilize or stronger evidence should emerge.",
            command=result["command"],
            dry_run=True,
            executed=False,
            result=str(result["result"]),
        )
