from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = ROOT / "experiment_runs"
DEFAULT_BENCHMARK_SUITE = ROOT / "benchmark_suite.yaml"
SESSION_PORT_FORWARD_DIR = ROOT / ".runtime" / "port_forwards"
CORE_DEPLOYMENTS = [
    "frontend",
    "cartservice",
    "checkoutservice",
    "currencyservice",
    "productcatalogservice",
    "recommendationservice",
    "shippingservice",
    "paymentservice",
    "emailservice",
    "adservice",
    "redis-cart",
    "opentelemetrycollector",
    "kube-state-metrics",
    "jaeger",
    "prometheus",
    "grafana",
]
CHAOS_RESOURCE_TYPES = [
    "podchaos",
    "stresschaos",
    "networkchaos",
    "dnschaos",
    "httpchaos",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ts_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def require_binary(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"Required binary not found in PATH: {name}")


def print_status(message: str) -> None:
    print(f"[{utc_now()}] {message}", flush=True)


def rel_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except Exception:
        return str(path.resolve())


def run_cmd(cmd: List[str], cwd: Path, log_path: Path) -> Dict[str, Any]:
    started = utc_now()
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    log_path.write_text(
        "COMMAND: " + " ".join(shlex.quote(part) for part in cmd) + "\n\n"
        + "STDOUT:\n"
        + proc.stdout
        + "\nSTDERR:\n"
        + proc.stderr
    )
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "started_at_utc": started,
        "finished_at_utc": utc_now(),
        "log": rel_path(log_path),
    }


def run_cmd_streaming(
    cmd: List[str],
    cwd: Path,
    log_path: Path,
    *,
    stdout_prefix: str = "",
) -> Dict[str, Any]:
    started = utc_now()
    with open(log_path, "w", encoding="utf-8") as handle:
        handle.write("COMMAND: " + " ".join(shlex.quote(part) for part in cmd) + "\n\n")
        handle.write("STREAMED OUTPUT:\n")
        handle.flush()
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            handle.write(line)
            handle.flush()
            sys.stdout.write(f"{stdout_prefix}{line}")
            sys.stdout.flush()
        proc.stdout.close()
        returncode = proc.wait()
    return {
        "cmd": cmd,
        "returncode": returncode,
        "started_at_utc": started,
        "finished_at_utc": utc_now(),
        "log": rel_path(log_path),
    }


def _stream_output(proc: subprocess.Popen[str], handle: Any, prefix: str, mirror_stdout: bool) -> None:
    if proc.stdout is None:
        return
    try:
        for line in proc.stdout:
            handle.write(line)
            handle.flush()
            if mirror_stdout:
                sys.stdout.write(f"{prefix}{line}")
                sys.stdout.flush()
    finally:
        proc.stdout.close()


def start_process(
    cmd: List[str],
    cwd: Path,
    log_path: Path,
    *,
    mirror_stdout: bool = False,
    stdout_prefix: str = "",
) -> subprocess.Popen[str]:
    handle = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    proc._agentscope_log_handle = handle  # type: ignore[attr-defined]
    stream_thread = threading.Thread(
        target=_stream_output,
        args=(proc, handle, stdout_prefix, mirror_stdout),
        daemon=True,
    )
    stream_thread.start()
    proc._agentscope_stream_thread = stream_thread  # type: ignore[attr-defined]
    return proc


def finish_process(proc: subprocess.Popen[str]) -> int:
    rc = proc.wait()
    stream_thread = getattr(proc, "_agentscope_stream_thread", None)
    if stream_thread is not None:
        stream_thread.join(timeout=2)
    handle = getattr(proc, "_agentscope_log_handle", None)
    if handle is not None:
        handle.close()
    return rc


def terminate_process(proc: subprocess.Popen[str]) -> int:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    stream_thread = getattr(proc, "_agentscope_stream_thread", None)
    if stream_thread is not None:
        stream_thread.join(timeout=2)
    handle = getattr(proc, "_agentscope_log_handle", None)
    if handle is not None:
        handle.close()
    return proc.returncode or 0


def bool_value(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise RuntimeError(f"Expected boolean value, got: {value!r}")


def int_value(value: Any, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    raise RuntimeError(f"Expected integer value, got: {value!r}")


def str_value(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    raise RuntimeError(f"Expected string value, got: {value!r}")


def list_value(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise RuntimeError(f"Expected list of strings, got: {value!r}")


def sanitize_name(name: str) -> str:
    cleaned = [ch.lower() if ch.isalnum() else "_" for ch in name]
    return "".join(cleaned).strip("_") or "experiment"


def endpoint_reachable(url: str, *, probe_path: str = "", timeout_seconds: int = 5) -> bool:
    target = url.rstrip("/")
    if probe_path:
        target = f"{target}{probe_path}"
    try:
        with urlopen(target, timeout=timeout_seconds):
            return True
    except Exception:
        return False


def epoch_to_utc(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sleep_with_progress(total_seconds: int, label: str) -> None:
    if total_seconds <= 0:
        return
    print_status(f"{label}: waiting {total_seconds}s")
    remaining = total_seconds
    step = 10 if total_seconds > 30 else 5 if total_seconds > 10 else 1
    while remaining > 0:
        chunk = min(step, remaining)
        time.sleep(chunk)
        remaining -= chunk
        if remaining > 0:
            print_status(f"{label}: {remaining}s remaining")
    print_status(f"{label}: done")


def _managed_port_forward_paths(service_name: str) -> tuple[Path, Path]:
    return (
        SESSION_PORT_FORWARD_DIR / f"{service_name}.log",
        SESSION_PORT_FORWARD_DIR / f"{service_name}.pid",
    )


def _read_pid(pid_path: Path) -> int | None:
    try:
        return int(pid_path.read_text().strip())
    except Exception:
        return None


def _pid_is_alive(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _terminate_pid(pid: int | None) -> None:
    if pid is None:
        return
    try:
        os.kill(pid, 15)
    except OSError:
        return
    deadline = time.time() + 5
    while time.time() < deadline:
        if not _pid_is_alive(pid):
            return
        time.sleep(0.2)
    try:
        os.kill(pid, 9)
    except OSError:
        return


def ensure_reusable_local_endpoint(namespace: str, service_name: str, local_url: str, probe_path: str) -> Dict[str, Any]:
    parsed = urlparse(local_url)
    host = (parsed.hostname or "").lower()
    port = parsed.port
    if host not in {"localhost", "127.0.0.1"} or port is None:
        return {"mode": "remote", "url": local_url}
    if endpoint_reachable(local_url, probe_path=probe_path):
        print_status(f"phase=port_forward: reusing session access for {service_name} at {local_url}")
        return {"mode": "reused", "url": local_url, "probe_path": probe_path, "state_dir": rel_path(SESSION_PORT_FORWARD_DIR)}

    SESSION_PORT_FORWARD_DIR.mkdir(parents=True, exist_ok=True)
    log_path, pid_path = _managed_port_forward_paths(service_name)
    pid = _read_pid(pid_path)
    if _pid_is_alive(pid):
        print_status(f"phase=port_forward: repairing stale session forward for {service_name} at {local_url}")
        _terminate_pid(pid)
        time.sleep(1)
    pid_path.unlink(missing_ok=True)

    cmd = ["kubectl", "port-forward", "-n", namespace, f"svc/{service_name}", f"{port}:{port}"]
    proc = start_process(cmd, ROOT, log_path)
    pid_path.write_text(f"{proc.pid}\n")

    deadline = time.time() + 20
    while time.time() < deadline:
        if proc.poll() is not None:
            break
        if endpoint_reachable(local_url, probe_path=probe_path, timeout_seconds=2):
            print_status(f"phase=port_forward: refreshed session access for {service_name} at {local_url}")
            return {
                "mode": "refreshed",
                "url": local_url,
                "probe_path": probe_path,
                "state_dir": rel_path(SESSION_PORT_FORWARD_DIR),
                "pid": proc.pid,
                "log": rel_path(log_path),
            }
        time.sleep(1)

    terminate_process(proc)
    pid_path.unlink(missing_ok=True)
    raise RuntimeError(
        f"local access for {service_name} at {local_url} is not reachable even after refreshing "
        f"the managed forward; see {rel_path(log_path)}"
    )


def read_detection_report(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def read_json_report(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}
