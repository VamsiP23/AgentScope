from __future__ import annotations

import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from typing import Any, List
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def require_binary(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"Required binary not found in PATH: {name}")


def run_cmd(cmd: List[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "cmd": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def prom_query(prom_url: str, query: str) -> dict[str, Any]:
    params = urlencode({"query": query})
    url = f"{prom_url.rstrip('/')}/api/v1/query?{params}"
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urlopen(url, timeout=10) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            break
        except (TimeoutError, URLError, OSError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.0 * (attempt + 1))
                continue
            raise RuntimeError(f"Prometheus query timed out or failed: {exc}") from exc
    else:
        raise RuntimeError(f"Prometheus query failed after retries: {last_error}")
    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus query failed: {payload}")
    return payload.get("data", {})
