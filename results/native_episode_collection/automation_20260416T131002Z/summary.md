# Native Episode Collection Summary

Run: `automation_20260416T131002Z`  
Timestamp: `2026-04-16T13:10:02Z`  
Workspace: `/Users/aarnavsawant/Documents/CS6365/AgentScope`

## Outcome

- New packaged episodes collected: 0
- Benchmark-ready episodes counted: 0
- Native faults applied: 0
- Failed or partial artifacts deleted: no
- Destructive cleanup used: no

Bulk collection was not started because the observability and Kubernetes API preflight failed. Starting native faults without readable Service/config state, replay-visible telemetry, and cleanup verification would violate the benchmark-validity gate.

## Preflight

- Python compile checks passed for capture, replay, evaluator, ReAct, Kubernetes evidence, evidence probe, and observability repair modules.
- Native fault backend, structured submit fields, fixed-label evaluator, diagnosis-only replay, auto-incrementing dataset capture, non-leaky initial-context generation, and Service/config evidence-layer code are present.
- All requested easy and medium native IDs are mapped in `benchmark_suite.yaml`, and their experiment files exist.
- Missing hard mappings/backend work:
  - `native_noisy_rollout_plus_service_port_mismatch_productcatalogservice`
  - `native_trace_dependency_bad_endpoint_frontend_cartservice`

## Blocker

`python3 scripts/repair_observability_access.py --namespace default` failed:

- Prometheus local access at `http://localhost:9090` is not reachable after managed forward refresh.
- Jaeger local access at `http://localhost:16686` is not reachable after managed forward refresh.
- Frontend local access at `http://localhost:8080` is not reachable after managed forward refresh.

The port-forward logs show:

```text
Unable to connect to the server: dial tcp 127.0.0.1:6443: connect: operation not permitted
```

`kubectl get pods -n default --no-headers` succeeded once and showed workload/observability pods Running, but a direct Service/config read for `productcatalogservice` failed with the same `127.0.0.1:6443` sandbox denial.

## Existing Package Audit

- `datasets/episodes/native_service_port_mismatch_productcatalogservice/native_service_port_mismatch_productcatalogservice_001.json`: initial context is non-leaky, but replay-visible `service_config` is absent. Not counted.
- `datasets/episodes/native_scale_zero_recommendationservice/native_scale_zero_recommendationservice_001.json`: initial context is non-leaky, but it was not freshly recollected or revalidated under the current evidence contract. Not counted.

## Scenario Counts

All requested easy, medium, and hard scenarios remain at 0 collected this run. The easy and medium scenarios are blocked by observability repair plus Kubernetes API/port-forward denial. The two hard scenarios are additionally blocked by missing mappings/backend implementation.

## Cleanup

No native fault was applied during this run. Cleanup-resource verification could not be completed honestly because Kubernetes resource reads are denied from this sandbox.

## Next Step

Run from an environment where `kubectl` Service/config reads and `kubectl port-forward` are permitted. Recollect `native_service_port_mismatch_productcatalogservice` and `native_service_selector_mismatch_cartservice` first, then audit replay `get_k8s_state(...)` outputs for decisive Service selector/targetPort evidence before counting any package.
