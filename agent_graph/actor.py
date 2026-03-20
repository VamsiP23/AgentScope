from __future__ import annotations

from typing import Any, Dict, List

from agent_graph.schemas import ActionPlan, Hypothesis
from agent_graph.tools.actions import ActionTools
from agent_graph.tools.kubernetes import KubernetesTools
from detectors.schemas import DetectionConfig


class Actor:
    def __init__(self, config: DetectionConfig, actions: ActionTools, k8s: KubernetesTools, dry_run: bool = True) -> None:
        self.config = config
        self.actions = actions
        self.k8s = k8s
        self.dry_run = dry_run

    def run(
        self,
        hypothesis: Hypothesis,
        attempted_actions: set[str],
        attempted_action_history: List[Dict[str, Any]] | None = None,
    ) -> ActionPlan:
        target = hypothesis.suspected_service or self.config.target_deployment
        attempted_action_history = attempted_action_history or []

        if hypothesis.id == "deployment_unavailable":
            dep = self.k8s.deployment_health(self.config.namespace, target)
            pod_status = self.k8s.deployment_pod_status(self.config.namespace, target)
            desired = int(dep.get("desired", 0))
            if desired == 0 and "restore_replicas" not in attempted_actions:
                result = self.actions.restore_replicas(self.config.namespace, target, replicas=1, dry_run=self.dry_run)
                return ActionPlan(
                    action="restore_replicas",
                    target=target,
                    rationale="deployment is scaled to zero; restore replicas first",
                    expected_signal="deployment available replicas should return to desired",
                    command=result["command"],
                    dry_run=self.dry_run,
                    executed=bool(result["executed"]),
                    result=str(result["result"]),
                )
            last_action = attempted_action_history[-1].get("action", "") if attempted_action_history else ""
            rollout_progressing = bool(pod_status.get("pod_count", 0)) and (
                bool(dep.get("available", 0))
                or bool(pod_status.get("progressing", False))
                or bool(pod_status.get("ready_pod_count", 0))
            )
            if last_action == "restore_replicas" and desired >= 1 and rollout_progressing:
                result = self.actions.wait_and_recheck(30)
                return ActionPlan(
                    action="wait_and_recheck",
                    target=target,
                    rationale="restore_replicas already triggered rollout progress; wait before restarting again",
                    expected_signal="available replicas should increase and frontend errors should begin to decline",
                    command=result["command"],
                    dry_run=True,
                    executed=False,
                    result=str(result["result"]),
                )
            if "rollout_restart" not in attempted_actions:
                result = self.actions.rollout_restart(self.config.namespace, target, dry_run=self.dry_run)
                return ActionPlan(
                    action="rollout_restart",
                    target=target,
                    rationale="deployment wants replicas but none are available",
                    expected_signal="deployment should recover availability and frontend errors should drop",
                    command=result["command"],
                    dry_run=self.dry_run,
                    executed=bool(result["executed"]),
                    result=str(result["result"]),
                )

        if hypothesis.id == "frontend_symptom_from_downstream_failure" and self.config.target_deployment:
            if "rollout_restart" not in attempted_actions:
                result = self.actions.rollout_restart(self.config.namespace, self.config.target_deployment, dry_run=self.dry_run)
                return ActionPlan(
                    action="rollout_restart",
                    target=self.config.target_deployment,
                    rationale="frontend is surfacing downstream errors; restart target deployment rather than frontend",
                    expected_signal="frontend error rate should decline after target recovery",
                    command=result["command"],
                    dry_run=self.dry_run,
                    executed=bool(result["executed"]),
                    result=str(result["result"]),
                )

        result = self.actions.wait_and_recheck(30)
        return ActionPlan(
            action="wait_and_recheck",
            target=target,
            rationale="no new safe action available; gather another observation window",
            expected_signal="error ratio should stabilize or new evidence should emerge",
            command=result["command"],
            dry_run=True,
            executed=False,
            result=str(result["result"]),
        )
