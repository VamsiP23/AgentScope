from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
    "gemini": "gemini-2.5-flash",
    "ollama": "llama3",
}

RATE_LIMIT_SECONDS = {
    "anthropic": 15,
    "openai": 15,
    "gemini": 20,
    "ollama": 0,
}

SERVICE_TOPOLOGY = {
    "frontend": ["productcatalogservice", "currencyservice", "cartservice", "recommendationservice", "checkoutservice"],
    "cartservice": ["redis-cart"],
    "productcatalogservice": [],
    "checkoutservice": ["cartservice", "productcatalogservice", "paymentservice", "currencyservice", "emailservice", "shippingservice"],
    "paymentservice": [],
    "currencyservice": [],
    "recommendationservice": ["productcatalogservice"],
    "shippingservice": [],
    "redis-cart": [],
}

BAD_ROLLOUT_MARKERS = (
    "imagepullbackoff",
    "errimagepull",
    "manifest unknown",
    "failed to pull image",
    "trying and failing to pull image",
    "image can't be pulled",
    "crashloopbackoff",
)

CONNECTION_ERROR_MARKERS = (
    "connection refused",
    "context deadline exceeded",
    "deadline exceeded",
    "i/o timeout",
    "timed out",
    "transport is closing",
    "unavailable",
)

RESOURCE_PRESSURE_MARKERS = (
    "oomkill",
    "oom killed",
    "out of memory",
    "throttl",
    "cpu cfs quota",
    "resource temporarily unavailable",
)

MAX_SEARCH_GUARDRAIL_ATTEMPTS = 6


def normalize_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized == "claude":
        return "anthropic"
    return normalized


def default_model(provider: str) -> str:
    if provider == "ollama":
        return os.environ.get("OLLAMA_MODEL", DEFAULT_MODELS["ollama"])
    if provider == "gemini":
        return os.environ.get("GEMINI_MODEL", DEFAULT_MODELS["gemini"])
    if provider == "openai":
        return os.environ.get("OPENAI_MODEL", DEFAULT_MODELS["openai"])
    if provider == "anthropic":
        return os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODELS["anthropic"])
    return DEFAULT_MODELS.get(provider, DEFAULT_MODELS["openai"])


def canonical_service_token(value: str) -> str:
    return "".join(char for char in value.lower() if char.isalnum())


def normalize_service_name(service: str) -> str:
    cleaned = service.strip().lower().lstrip("/")
    if not cleaned:
        return ""
    canonical = canonical_service_token(cleaned)
    for known_service in SERVICE_TOPOLOGY:
        if canonical_service_token(known_service) == canonical:
            return known_service
    tail = cleaned.split("/")[-1].split(".")[-1]
    tail_canonical = canonical_service_token(tail)
    for known_service in SERVICE_TOPOLOGY:
        if canonical_service_token(known_service) == tail_canonical:
            return known_service
    return tail


def collect_output_text(output: Dict[str, Any]) -> str:
    parts: List[str] = []
    if output.get("error"):
        parts.append(str(output.get("error")))
    for line in output.get("error_lines", []) or []:
        parts.append(str(line))
    for event in output.get("recent_events", []) or []:
        parts.append(str((event or {}).get("reason", "")))
        parts.append(str((event or {}).get("message", "")))
    for pod in output.get("pods", []) or []:
        parts.append(str((pod or {}).get("log_error", "")))
        for line in (pod or {}).get("error_lines", []) or []:
            parts.append(str(line))
    for span in output.get("error_spans", []) or []:
        parts.append(str((span or {}).get("service", "")))
        parts.append(str((span or {}).get("error_message", "")))
    for hop in output.get("call_chain", []) or []:
        parts.append(str((hop or {}).get("error_message", "")))
        parts.append(str((hop or {}).get("operation", "")))
        parts.append(str((hop or {}).get("peer_service", "")))
    return " ".join(part for part in parts if part)


def extract_markers(text: str, markers: Tuple[str, ...]) -> List[str]:
    found: List[str] = []
    for marker in markers:
        if marker in text and marker not in found:
            found.append(marker)
    return found


def metrics_signal_summary(metrics: Dict[str, Any]) -> str:
    resource_metrics_available = bool(metrics.get("resource_metrics_available", False))
    application_metrics_available = bool(metrics.get("application_metrics_available", True))
    cpu_usage = float(metrics.get("cpu_usage", 0.0) or 0.0) if metrics.get("cpu_usage") is not None else 0.0
    cpu_pct_limit = float(metrics.get("cpu_utilization_pct_of_limit", 0.0) or 0.0) if metrics.get("cpu_utilization_pct_of_limit") is not None else 0.0
    cpu_throttling_ratio = float(metrics.get("cpu_throttling_ratio", 0.0) or 0.0) if metrics.get("cpu_throttling_ratio") is not None else 0.0
    memory_pct_limit = float(metrics.get("memory_utilization_pct_of_limit", 0.0) or 0.0) if metrics.get("memory_utilization_pct_of_limit") is not None else 0.0
    error_rate = float(metrics.get("error_rate", 0.0) or 0.0) if metrics.get("error_rate") is not None else 0.0
    latency_ms = float(metrics.get("p99_latency_ms", 0.0) or 0.0) if metrics.get("p99_latency_ms") is not None else 0.0

    if not application_metrics_available and not resource_metrics_available:
        return "metrics_unavailable"
    if not resource_metrics_available:
        error_band = "high" if error_rate >= 0.05 else "moderate" if error_rate >= 0.01 else "low"
        latency_band = "high" if latency_ms >= 1000 else "elevated" if latency_ms >= 250 else "low"
        return f"resource_metrics=missing error_rate={error_band} latency={latency_band}"

    cpu_band = "high" if cpu_pct_limit >= 80 or cpu_usage >= 0.15 else "moderate" if cpu_pct_limit >= 50 or cpu_usage >= 0.08 else "low"
    throttle_band = "high" if cpu_throttling_ratio >= 0.2 else "moderate" if cpu_throttling_ratio >= 0.05 else "low"
    memory_band = "high" if memory_pct_limit >= 85 else "moderate" if memory_pct_limit >= 65 else "low"
    error_band = "high" if error_rate >= 0.05 else "moderate" if error_rate >= 0.01 else "low"
    latency_band = "high" if latency_ms >= 1000 else "elevated" if latency_ms >= 250 else "low"
    return f"cpu={cpu_band} throttle={throttle_band} memory={memory_band} error_rate={error_band} latency={latency_band}"


def service_unavailable(output: Dict[str, Any]) -> bool:
    desired = int(output.get("desired_replicas", 0) or 0)
    available = int(output.get("available_replicas", 0) or 0)
    return desired > 0 and available < desired


def service_healthy(output: Dict[str, Any]) -> bool:
    desired = int(output.get("desired_replicas", 0) or 0)
    available = int(output.get("available_replicas", 0) or 0)
    return desired > 0 and available >= desired and not bool(output.get("rollout_progressing", False))


def dominant_trace_link(trace_output: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    dominant: Optional[Dict[str, Any]] = None
    for hop in trace_output.get("call_chain", []) or []:
        caller = normalize_service_name(str((hop or {}).get("service", "")))
        callee = normalize_service_name(str((hop or {}).get("peer_service", "")))
        if not caller or not callee or caller == callee:
            continue
        candidate = {
            "caller": caller,
            "callee": callee,
            "pct_of_total": float((hop or {}).get("pct_of_total", 0.0) or 0.0),
            "duration_ms": float((hop or {}).get("duration_ms", 0.0) or 0.0),
            "error": bool((hop or {}).get("error", False)),
            "error_message": str((hop or {}).get("error_message", "")),
        }
        if dominant is None or candidate["pct_of_total"] > dominant["pct_of_total"]:
            dominant = candidate
    return dominant
