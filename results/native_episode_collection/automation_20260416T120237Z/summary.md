# Native Episode Collection Summary - 2026-04-16T12:02:37Z

## Outcome

- New packaged episodes: 0
- Benchmark-ready episodes counted: 0
- Native faults applied: no
- Destructive cleanup used: no

No live collection was run. Observability repair failed for Prometheus, Jaeger, and frontend local access, and follow-up Kubernetes API calls/port-forward attempts were denied with `dial tcp 127.0.0.1:6443: connect: operation not permitted`. Applying faults under that condition would risk failed cleanup and incomplete evidence, so the benchmark-validity gate blocked collection.

## Preflight

- Memory was read and the dirty main workspace was preserved.
- `py_compile` passed for capture, replay, evaluator, ReAct, Kubernetes evidence, evidence probe, benchmark runner, and observability repair modules.
- Native structured submit fields, fixed-label evaluator, diagnosis-only replay, auto-incrementing dataset capture, non-leaky initial-context generation, and Service/config evidence-layer code are present in the main workspace.
- All 12 requested easy/medium mappings are present and point to existing experiment files.
- The two pinned hard scenario IDs are still missing suite/backend implementation:
  - `native_noisy_rollout_plus_service_port_mismatch_productcatalogservice`
  - `native_trace_dependency_bad_endpoint_frontend_cartservice`

## Observability Blocker

`python3 scripts/repair_observability_access.py --namespace default` returned `ok=false`:

- Prometheus: local access at `http://localhost:9090` not reachable after refreshing the managed forward.
- Jaeger: local access at `http://localhost:16686` not reachable after refreshing the managed forward.
- Frontend: local access at `http://localhost:8080` not reachable after refreshing the managed forward.

`kubectl get pods -n default --no-headers` succeeded once and showed workloads/observability pods Running. A direct Service read and cleanup/resource verification commands failed with the same API denial against `127.0.0.1:6443`, and the port-forward logs show the same failure.

## Scenario Counts

| Scenario | Target | Collected | Reason |
| --- | ---: | ---: | --- |
| `native_service_port_mismatch_productcatalogservice` | 3 | 0 | Blocked by observability/API access; existing `_001` is clean but lacks replay Service/config tool-call evidence. |
| `native_service_selector_mismatch_cartservice` | 3 | 0 | Blocked before fault application. |
| `native_bad_image_productcatalogservice` | 3 | 0 | Blocked before fault application. |
| `native_bad_probe_cartservice` | 3 | 0 | Blocked before fault application. |
| `native_scale_zero_recommendationservice` | 3 | 0 | Blocked; existing `_001` is clean but lacks replay tool-call evidence in the inspected package. |
| `native_pod_delete_cartservice` | 3 | 0 | Blocked before fault application. |
| `native_dependency_bad_endpoint_frontend_cartservice` | 3 | 0 | Blocked before fault application. |
| `native_cpu_limit_throttle_checkoutservice` | 3 | 0 | Blocked before fault application. |
| `native_memory_limit_oom_cartservice` | 3 | 0 | Blocked before fault application. |
| `native_cpu_pressure_stress_job` | 3 | 0 | Blocked before fault application. |
| `native_memory_pressure_stress_job` | 3 | 0 | Blocked before fault application. |
| `native_bad_env_checkoutservice_email` | 3 | 0 | Blocked before fault application. |
| `native_noisy_rollout_plus_service_port_mismatch_productcatalogservice` | 3 | 0 | Missing hard scenario mapping/backend; live access also blocked. |
| `native_trace_dependency_bad_endpoint_frontend_cartservice` | 3 | 0 | Missing hard scenario mapping/backend; live access also blocked. |

## Evidence And Replay

- Full-evidence audits run: 0 new episodes.
- Evidence-insufficient packages counted: 0.
- Existing inspected packages were not counted:
  - `/Users/aarnavsawant/Documents/CS6365/AgentScope/datasets/episodes/native_service_port_mismatch_productcatalogservice/native_service_port_mismatch_productcatalogservice_001.json`
  - `/Users/aarnavsawant/Documents/CS6365/AgentScope/datasets/episodes/native_scale_zero_recommendationservice/native_scale_zero_recommendationservice_001.json`
- Replay smoke runs: 0.
- Gemini replay runs: 0.
- Fixed-label evaluations: 0.

## Cleanup

No native faults were applied during this run. Cleanup verification is blocked because API resource checks are denied by the sandbox.

## Next Step

Rerun from an environment where `kubectl` Service/config reads and port-forward are permitted, then recollect `native_service_port_mismatch_productcatalogservice` and `native_service_selector_mismatch_cartservice` first so packaged replay outputs include decisive Service/config evidence.
