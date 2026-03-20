from __future__ import annotations

from typing import Dict, List

SERVICE_TOPOLOGY: Dict[str, Dict[str, object]] = {
    "frontend": {
        "role": "user-facing web entrypoint",
        "depends_on": [
            "productcatalogservice",
            "cartservice",
            "recommendationservice",
            "currencyservice",
            "checkoutservice",
            "adservice",
        ],
        "request_paths": ["homepage", "product page", "cart", "checkout"],
    },
    "productcatalogservice": {
        "role": "product information service",
        "depends_on": [],
        "request_paths": ["homepage", "product page", "recommendations"],
    },
    "cartservice": {
        "role": "shopping cart state service",
        "depends_on": ["redis-cart"],
        "request_paths": ["add to cart", "cart page", "checkout"],
    },
    "redis-cart": {
        "role": "cart backing datastore",
        "depends_on": [],
        "request_paths": ["add to cart", "cart page", "checkout"],
    },
    "checkoutservice": {
        "role": "order orchestration service",
        "depends_on": [
            "cartservice",
            "paymentservice",
            "shippingservice",
            "emailservice",
            "productcatalogservice",
            "currencyservice",
        ],
        "request_paths": ["checkout"],
    },
    "paymentservice": {
        "role": "payment authorization service",
        "depends_on": [],
        "request_paths": ["checkout"],
    },
    "shippingservice": {
        "role": "shipping quote and fulfillment service",
        "depends_on": [],
        "request_paths": ["checkout"],
    },
    "emailservice": {
        "role": "order confirmation service",
        "depends_on": [],
        "request_paths": ["checkout"],
    },
    "recommendationservice": {
        "role": "product recommendation service",
        "depends_on": ["productcatalogservice"],
        "request_paths": ["homepage", "product page"],
    },
    "currencyservice": {
        "role": "currency conversion service",
        "depends_on": [],
        "request_paths": ["homepage", "product page", "checkout"],
    },
    "adservice": {
        "role": "advertising service",
        "depends_on": [],
        "request_paths": ["homepage"],
    },
}


def service_context(service: str) -> Dict[str, object]:
    return SERVICE_TOPOLOGY.get(service, {"role": "unknown", "depends_on": [], "request_paths": []})


def downstream_dependencies(service: str) -> List[str]:
    ctx = service_context(service)
    return list(ctx.get("depends_on", []))


def upstream_surfaces(service: str) -> List[str]:
    rows: List[str] = []
    for candidate, meta in SERVICE_TOPOLOGY.items():
        depends_on = meta.get("depends_on", [])
        if isinstance(depends_on, list) and service in depends_on:
            rows.append(candidate)
    return rows


def topology_summary(service: str) -> str:
    ctx = service_context(service)
    role = ctx.get("role", "unknown")
    depends_on = ctx.get("depends_on", [])
    request_paths = ctx.get("request_paths", [])
    return (
        f"service={service} role={role}; depends_on={depends_on}; request_paths={request_paths}"
    )
