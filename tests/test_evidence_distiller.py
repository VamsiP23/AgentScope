from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_graph.evidence_distiller import EvidenceDistiller, add_cross_record_evidence, select_compact_evidence_records


def test_k8s_service_port_mismatch_compacts_without_raw_dump() -> None:
    raw = {
        "service": "productcatalogservice",
        "call_id": "abc",
        "timestamp": "2026-04-18T00:00:00Z",
        "desired_replicas": 1,
        "available_replicas": 1,
        "rollout_progressing": False,
        "restart_count": 0,
        "pod_phases": [{"pod_name": "pod-1", "phase": "Running", "ready": True, "restart_count": 0}],
        "service_config_summary": {
            "selector": {"app": "productcatalogservice"},
            "selected_pod_count": 1,
            "deployment_pod_count": 1,
            "service_ports": [{"port": 3550, "targetPort": 1}],
            "container_ports": [{"container": "server", "containerPort": 3550}],
            "endpoint_counts": {"effective_ready": 1, "effective_not_ready": 0},
            "service_port_alignment": {
                "aligned": False,
                "mismatches": [{"service_port": 3550, "targetPort": 1}],
            },
            "anomalies": ["service_target_port_mismatch"],
        },
        "raw_output": {"large": "payload"},
    }

    compact = EvidenceDistiller().distill("get_k8s_state", raw)

    assert compact["status"] == "anomalous"
    assert "raw_output" not in compact
    assert compact["raw_refs"][1]["artifact"] == "packaged_raw_payload"
    assert any("targetPort=1" in str(fact) for fact in compact["key_facts"])
    assert any(
        item.get("type") == "port_inconsistency" and item.get("scope") == "service"
        for item in compact["anomalies"]
    )
    assert "service_port_alignment_mismatch" not in str(compact)


def test_logs_group_error_patterns() -> None:
    raw = {
        "service": "frontend",
        "error_lines": [
            "rpc error: code = Unavailable desc = connection refused",
            "context deadline exceeded",
        ],
    }

    compact = EvidenceDistiller().distill("get_logs", raw)

    assert compact["status"] == "anomalous"
    assert any(item.get("type") == "log_signal_patterns" for item in compact["anomalies"])
    assert "connection refused" in str(compact["key_facts"])


def test_metrics_negative_evidence_for_healthy_service() -> None:
    raw = {
        "service": "cartservice",
        "metrics": {
            "error_rate": 0.0,
            "p95_latency_ms": 10.0,
            "p99_latency_ms": 20.0,
            "request_rps": 5.0,
            "cpu_utilization_pct_of_limit": 20.0,
            "cpu_throttling_ratio": 0.0,
            "memory_utilization_pct_of_limit": 30.0,
            "resource_metrics_available": True,
            "application_metrics_available": True,
        },
    }

    compact = EvidenceDistiller().distill("get_metrics", raw)

    assert compact["status"] == "ok"
    assert compact["anomalies"] == []
    assert compact["negative_evidence"]


def test_k8s_lifecycle_scale_zero_and_pod_replacement_facts() -> None:
    distiller = EvidenceDistiller()
    scale_zero = distiller.distill(
        "get_k8s_state",
        {
            "service": "recommendationservice",
            "desired_replicas": 0,
            "available_replicas": 0,
            "pod_phases": [],
            "recent_events": [
                {
                    "reason": "ScalingReplicaSet",
                    "message": "Scaled down replica set recommendationservice to 0 from 1",
                    "type": "Normal",
                }
            ],
        },
    )
    assert any(item.get("type") == "desired_replicas_zero" for item in scale_zero["anomalies"])
    assert any(item.get("type") == "deployment_scaled_down_to_zero_event" for item in scale_zero["anomalies"])

    pod_replace = distiller.distill(
        "get_k8s_state",
        {
            "service": "cartservice",
            "desired_replicas": 1,
            "available_replicas": 0,
            "rollout_progressing": True,
            "pod_phases": [{"pod_name": "cart-1", "phase": "Running", "ready": False, "restart_count": 0}],
            "recent_events": [
                {"reason": "SuccessfulDelete", "message": "Deleted pod: cart-old", "type": "Normal"},
                {"reason": "SuccessfulCreate", "message": "Created pod: cart-new", "type": "Normal"},
            ],
        },
    )
    assert any(item.get("type") == "pod_lifecycle_replacement_events" for item in pod_replace["anomalies"])
    assert any("without image-pull failure" in item for item in pod_replace["negative_evidence"])


def test_metrics_surface_external_pressure_profile_without_app_saturation() -> None:
    raw = {
        "service": "frontend",
        "metrics": {
            "error_rate": 0.0,
            "p99_latency_ms": 900.0,
            "cpu_utilization_pct_of_limit": 25.0,
            "cpu_throttling_ratio": 0.02,
            "memory_utilization_pct_of_limit": 30.0,
            "resource_metrics_available": True,
            "application_metrics_available": True,
        },
    }

    compact = EvidenceDistiller().distill("get_metrics", raw)

    assert compact["status"] == "anomalous"
    assert any(item.get("type") == "latency_or_errors_without_app_resource_saturation" for item in compact["anomalies"])
    assert any("App-local CPU" in item for item in compact["negative_evidence"])


def test_cluster_resource_context_sanitizes_external_pressure_evidence() -> None:
    compact = EvidenceDistiller().distill(
        "get_cluster_resource_context",
        {
            "service": "frontend",
            "active_non_app_workloads": [
                {"phase": "Running", "node": "worker-a", "resource_hint": "cpu"},
            ],
            "resource_pressure": {"resource": "cpu", "scope": "node_or_namespace"},
            "app_local_saturation_absent": True,
            "raw_refs": [{"artifact": "source_run_detector_snapshot", "field": "active_stress_jobs"}],
        },
    )

    assert compact["status"] == "anomalous"
    assert any(item.get("type") == "external_resource_pressure" for item in compact["anomalies"])
    assert any("active_non_app_workloads" in item for item in compact["key_facts"] if isinstance(item, dict))
    assert "native_stress_job" not in str(compact)
    assert "agentscope-cpu-pressure" not in str(compact)


def test_deployment_env_addresses_are_parsed_without_label_leak() -> None:
    raw = {
        "service": "frontend",
        "desired_replicas": 1,
        "available_replicas": 1,
        "deployment_config": {
            "env": [
                {"container": "server", "name": "CART_SERVICE_ADDR", "value": "cartservice:1", "value_redacted": False},
                {"container": "server", "name": "CHECKOUT_SERVICE_ADDR", "value": "checkoutservice:5050", "value_redacted": False},
            ]
        },
    }

    compact = EvidenceDistiller().distill("get_k8s_state", raw)

    assert any("configured_dependency_addresses" in item for item in compact["key_facts"] if isinstance(item, dict))
    assert any(
        item.get("type") == "port_inconsistency" and item.get("scope") == "dependency_config"
        for item in compact["anomalies"]
    )
    assert "unusual_dependency_env_port" not in str(compact)
    assert "native_dependency_bad_endpoint" not in str(compact)


def test_cross_record_dependency_env_port_comparison() -> None:
    rows = [
        {
            "tool": "get_k8s_state",
            "inputs": {"service": "checkoutservice"},
            "evidence": {
                "service": "checkoutservice",
                "key_facts": [
                    {
                        "configured_dependency_addresses": [
                            {
                                "env": "EMAIL_SERVICE_ADDR",
                                "dependency_hint": "email",
                                "host": "emailservice",
                                "port": 5999,
                            }
                        ]
                    }
                ],
                "anomalies": [],
                "negative_evidence": [],
            },
        },
        {
            "tool": "get_k8s_state",
            "inputs": {"service": "emailservice"},
            "evidence": {
                "service": "emailservice",
                "key_facts": [
                    "Service ports/targetPorts: port=5000 targetPort=8080 name=grpc.",
                    "Selected pod container ports: container=server port=8080 name=.",
                ],
                "anomalies": [],
                "negative_evidence": [],
            },
        },
    ]

    compact_rows = add_cross_record_evidence(rows)
    checkout = compact_rows[0]["evidence"]

    assert any(
        item.get("type") == "port_inconsistency" and item.get("scope") == "dependency"
        for item in checkout["anomalies"]
    )
    assert any("observed_service_ports" in item for item in checkout["key_facts"] if isinstance(item, dict))
    assert "dependency_env_port_mismatch_with_observed_service" not in str(checkout)
    assert "dependency_env_service_port_comparison" not in str(checkout)
    assert "native_bad_env" not in str(checkout)


def test_compact_selection_keeps_log_mentioned_dependency_state() -> None:
    rows = [
        {
            "tool": "get_k8s_state",
            "inputs": {"service": "checkoutservice"},
            "evidence": {
                "service": "checkoutservice",
                "key_facts": [
                    {
                        "configured_dependency_addresses": [
                            {"env": "EMAIL_SERVICE_ADDR", "host": "emailservice", "port": 5999},
                            {"env": "CART_SERVICE_ADDR", "host": "cartservice", "port": 7070},
                        ]
                    }
                ],
                "anomalies": [],
                "negative_evidence": [],
            },
        },
        {"tool": "get_metrics", "inputs": {"service": "checkoutservice"}, "evidence": {"service": "checkoutservice"}},
        {
            "tool": "get_logs",
            "inputs": {"service": "checkoutservice"},
            "evidence": {"service": "checkoutservice", "key_facts": ["timeout dialing emailservice:5999"]},
        },
        {"tool": "get_k8s_state", "inputs": {"service": "cartservice"}, "evidence": {"service": "cartservice", "key_facts": []}},
        {
            "tool": "get_k8s_state",
            "inputs": {"service": "emailservice"},
            "evidence": {
                "service": "emailservice",
                "key_facts": ["Service ports/targetPorts: port=5000 targetPort=8080 name=grpc."],
                "anomalies": [],
                "negative_evidence": [],
            },
        },
    ]

    selected = select_compact_evidence_records(rows, max_records=4)

    assert any(row["inputs"].get("service") == "emailservice" for row in selected)
    checkout = next(row["evidence"] for row in selected if row["inputs"].get("service") == "checkoutservice")
    assert any(
        item.get("type") == "port_inconsistency" and item.get("scope") == "dependency"
        for item in checkout["anomalies"]
    )
