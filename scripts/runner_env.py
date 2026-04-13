from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

from runner_common import DEFAULT_BENCHMARK_SUITE, ROOT, bool_value, list_value, str_value


def load_yaml(path: Path) -> Dict[str, Any]:
    payload = yaml.safe_load(path.read_text())
    if not isinstance(payload, dict):
        raise RuntimeError(f"Experiment file must parse to a mapping: {path}")
    return payload


def build_fault_apply_cmd(namespace: str, fault: Dict[str, Any]) -> List[str]:
    apply_cmd = list_value(fault.get("apply_cmd"))
    if apply_cmd:
        return apply_cmd

    filepath = str_value(fault.get("filepath"))
    if not filepath:
        raise RuntimeError("fault.filepath or fault.apply_cmd is required")

    fault_path = Path(filepath)
    if not fault_path.is_absolute():
        fault_path = (ROOT / fault_path).resolve()
    return ["python3", "-m", "faults.cli", "apply", str(fault_path)]


def build_fault_revert_cmd(namespace: str, fault: Dict[str, Any]) -> List[str]:
    revert_cmd = list_value(fault.get("revert_cmd"))
    if revert_cmd:
        return revert_cmd

    filepath = str_value(fault.get("filepath"))
    if not filepath:
        raise RuntimeError("fault.filepath or fault.revert_cmd is required")

    fault_path = Path(filepath)
    if not fault_path.is_absolute():
        fault_path = (ROOT / fault_path).resolve()
    return ["python3", "-m", "faults.cli", "revert", str(fault_path)]


def build_reset_cmd(namespace: str, reset_cfg: Dict[str, Any]) -> List[str]:
    cmd = ["./scripts/reset_cluster.sh", "-n", namespace]
    context = str_value(reset_cfg.get("context"))
    manifest = str_value(reset_cfg.get("manifest"))
    if context:
        cmd.extend(["-c", context])
    if manifest:
        cmd.extend(["-m", manifest])
    if bool_value(reset_cfg.get("kill_port_forwards"), False):
        cmd.append("-p")
    if bool_value(reset_cfg.get("refresh_observability"), False):
        cmd.append("-o")
    cmd.extend(list_value(reset_cfg.get("args")))
    return cmd


__all__ = [
    "DEFAULT_BENCHMARK_SUITE",
    "build_fault_apply_cmd",
    "build_fault_revert_cmd",
    "build_reset_cmd",
    "load_yaml",
]
