from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import List

ANN_PREFIX = "agentscope.io"


@dataclass
class FaultContext:
    namespace: str = "default"
    target: str = ""
    latency: str = "3s"
    replicas: int = 1
    cpu_limit: str = "100m"
    cpu_request: str = "50m"


def require_kubectl() -> None:
    if shutil.which("kubectl") is None:
        print("kubectl is required but not installed.", file=sys.stderr)
        raise SystemExit(1)


def run_kubectl(args: List[str], capture: bool = False) -> str:
    proc = subprocess.run(
        ["kubectl", *args],
        capture_output=capture,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip() or "kubectl command failed"
        raise RuntimeError(err)
    return (proc.stdout or "").strip()


def set_annotation(namespace: str, deploy: str, key: str, value: str) -> None:
    run_kubectl(["annotate", "deployment", deploy, "-n", namespace, f"{key}={value}", "--overwrite"])


def remove_annotation(namespace: str, deploy: str, key: str) -> None:
    proc = subprocess.run(
        ["kubectl", "annotate", "deployment", deploy, "-n", namespace, f"{key}-"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode not in (0, 1):
        err = proc.stderr.strip() or proc.stdout.strip() or "annotation removal failed"
        raise RuntimeError(err)


def get_annotation(namespace: str, deploy: str, key: str) -> str:
    escaped = key.replace(".", "\\.").replace("/", "\\/")
    return run_kubectl(
        ["get", "deployment", deploy, "-n", namespace, "-o", f"jsonpath={{.metadata.annotations.{escaped}}}"],
        capture=True,
    )


def get_replicas(namespace: str, deploy: str) -> str:
    return run_kubectl(
        ["get", "deployment", deploy, "-n", namespace, "-o", "jsonpath={.spec.replicas}"],
        capture=True,
    )
