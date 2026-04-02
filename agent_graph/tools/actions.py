from __future__ import annotations

import json
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

    def rollout_undo(self, namespace: str, target: str, dry_run: bool = True) -> Dict[str, object]:
        cmd = ["kubectl", "rollout", "undo", f"deployment/{target}", "-n", namespace]
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

    def restart_pod(self, namespace: str, pod_name: str, dry_run: bool = True) -> Dict[str, object]:
        return self.delete_pod(namespace, pod_name, dry_run=dry_run)

    def patch_resources(
        self,
        namespace: str,
        target: str,
        *,
        container: str = "server",
        cpu_request: str = "",
        cpu_limit: str = "",
        memory_request: str = "",
        memory_limit: str = "",
        dry_run: bool = True,
    ) -> Dict[str, object]:
        patch = {
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": container,
                                "resources": {
                                    "requests": {},
                                    "limits": {},
                                },
                            }
                        ]
                    }
                }
            }
        }
        requests = patch["spec"]["template"]["spec"]["containers"][0]["resources"]["requests"]
        limits = patch["spec"]["template"]["spec"]["containers"][0]["resources"]["limits"]

        if cpu_request:
            requests["cpu"] = cpu_request
        if memory_request:
            requests["memory"] = memory_request
        if cpu_limit:
            limits["cpu"] = cpu_limit
        if memory_limit:
            limits["memory"] = memory_limit

        if not requests:
            patch["spec"]["template"]["spec"]["containers"][0]["resources"].pop("requests")
        if not limits:
            patch["spec"]["template"]["spec"]["containers"][0]["resources"].pop("limits")

        cmd = [
            "kubectl",
            "patch",
            f"deployment/{target}",
            "-n",
            namespace,
            "--type",
            "strategic",
            "-p",
            json.dumps(patch, separators=(",", ":")),
        ]
        if dry_run:
            return {"command": cmd, "executed": False, "result": "dry_run"}
        result = run_cmd(cmd)
        return {"command": cmd, "executed": True, "result": result}

    def wait_and_monitor(self, seconds: int = 30) -> Dict[str, object]:
        return {
            "command": ["sleep", str(seconds)],
            "executed": False,
            "result": f"suggested wait {seconds}s before recheck",
        }

    def wait_and_recheck(self, seconds: int = 30) -> Dict[str, object]:
        return self.wait_and_monitor(seconds)
