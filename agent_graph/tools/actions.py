from __future__ import annotations

from typing import Dict, List

from detectors.utils import run_cmd


class ActionTools:
    def scale_replicas(self, namespace: str, target: str, replicas: int, dry_run: bool = True) -> Dict[str, object]:
        cmd = ["kubectl", "scale", "deployment", target, "-n", namespace, f"--replicas={replicas}"]
        if dry_run:
            return {"command": cmd, "executed": False, "result": "dry_run"}
        result = run_cmd(cmd)
        return {"command": cmd, "executed": True, "result": result}

    def restore_replicas(self, namespace: str, target: str, replicas: int = 1, dry_run: bool = True) -> Dict[str, object]:
        return self.scale_replicas(namespace, target, replicas=replicas, dry_run=dry_run)

    def rollout_restart(self, namespace: str, target: str, dry_run: bool = True) -> Dict[str, object]:
        cmd = ["kubectl", "rollout", "restart", f"deployment/{target}", "-n", namespace]
        if dry_run:
            return {"command": cmd, "executed": False, "result": "dry_run"}
        result = run_cmd(cmd)
        return {"command": cmd, "executed": True, "result": result}

    def delete_pod(self, namespace: str, pod_name: str, dry_run: bool = True) -> Dict[str, object]:
        cmd = ["kubectl", "delete", "pod", pod_name, "-n", namespace]
        if dry_run:
            return {"command": cmd, "executed": False, "result": "dry_run"}
        result = run_cmd(cmd)
        return {"command": cmd, "executed": True, "result": result}

    def wait_and_recheck(self, seconds: int = 30) -> Dict[str, object]:
        return {
            "command": ["sleep", str(seconds)],
            "executed": False,
            "result": f"suggested wait {seconds}s before recheck",
        }
