# Native Episode Collection Summary

- Run: `automation_20260416T150225Z`
- Timestamp: `2026-04-16T15:02:25Z`
- Workspace: `/Users/aarnavsawant/Documents/CS6365/AgentScope`
- Target: 3 packaged episodes per scenario

## Outcome

Collected 0 new packaged episodes and counted 0 benchmark-ready episodes.

No native fault was applied, no failed artifact was deleted, and no destructive cleanup was used.

## Preflight

- `py_compile` passed for capture, replay, evaluator, ReAct, Kubernetes tool, evidence probe, observability repair, and native fault modules.
- Native fault backend, structured submit fields, fixed-label evaluator, auto-incrementing capture output, non-leaky initial-context generation, replay diagnosis-only mode, and Service/config evidence-layer code are present.
- Easy and medium native benchmark-suite mappings are present and mapped experiment files exist.
- Pinned hard scenario mappings/backend implementation are still missing:
  - `native_noisy_rollout_plus_service_port_mismatch_productcatalogservice`
  - `native_trace_dependency_bad_endpoint_frontend_cartservice`

## Blocker

`python3 scripts/repair_observability_access.py --namespace default` failed for Prometheus, Jaeger, and frontend local access:

- Prometheus: local access at `http://localhost:9090` not reachable after refreshing the managed forward.
- Jaeger: local access at `http://localhost:16686` not reachable after refreshing the managed forward.
- Frontend: local access at `http://localhost:8080` not reachable after refreshing the managed forward.

`kubectl get pods -n default --no-headers` succeeded once and showed workload and observability pods Running. Subsequent Service, Deployment, EndpointSlice, and port-forward reads failed with:

`Unable to connect to the server: dial tcp 127.0.0.1:6443: connect: operation not permitted`

Because stable Kubernetes API and observability access were unavailable, no evidence probe was run. Running live faults under this condition would not satisfy the full-evidence or evidence-sufficiency gates.

## Scenario Counts

| Scenario | Target | Collected | Reason |
| --- | ---: | ---: | --- |
| `native_service_port_mismatch_productcatalogservice` | 3 | 0 | API/port-forward access blocked; existing `_001` lacks replay-visible Service/config evidence |
| `native_service_selector_mismatch_cartservice` | 3 | 0 | API/port-forward access blocked |
| `native_bad_image_productcatalogservice` | 3 | 0 | API/port-forward access blocked |
| `native_bad_probe_cartservice` | 3 | 0 | API/port-forward access blocked |
| `native_scale_zero_recommendationservice` | 3 | 0 | API/port-forward access blocked; existing `_001` not freshly revalidated |
| `native_pod_delete_cartservice` | 3 | 0 | API/port-forward access blocked |
| `native_dependency_bad_endpoint_frontend_cartservice` | 3 | 0 | API/port-forward access blocked |
| `native_cpu_limit_throttle_checkoutservice` | 3 | 0 | API/port-forward access blocked |
| `native_memory_limit_oom_cartservice` | 3 | 0 | API/port-forward access blocked |
| `native_cpu_pressure_stress_job` | 3 | 0 | API/port-forward access blocked |
| `native_memory_pressure_stress_job` | 3 | 0 | API/port-forward access blocked |
| `native_bad_env_checkoutservice_email` | 3 | 0 | API/port-forward access blocked |
| `native_noisy_rollout_plus_service_port_mismatch_productcatalogservice` | 3 | 0 | Mapping/backend still missing; live access blocked |
| `native_trace_dependency_bad_endpoint_frontend_cartservice` | 3 | 0 | Mapping/backend still missing; live access blocked |

## Existing Packages

- `/Users/aarnavsawant/Documents/CS6365/AgentScope/datasets/episodes/native_service_port_mismatch_productcatalogservice/native_service_port_mismatch_productcatalogservice_001.json`: initial context is clean, but the package has no replay-visible `service_config`, so the decisive Service targetPort/container-port evidence is absent. Not counted.
- `/Users/aarnavsawant/Documents/CS6365/AgentScope/datasets/episodes/native_scale_zero_recommendationservice/native_scale_zero_recommendationservice_001.json`: initial context is clean, but it was not freshly regenerated or replay-audited after the evidence-layer change. Not counted.

## Replay And Cleanup

No replay/Gemini evaluation was run because no newly collected benchmark-ready episode existed. No cleanup was needed because no fault was applied. Full cleanup verification could not be completed after Kubernetes API access became denied.

## Next Step

Run from a context with stable access to `https://127.0.0.1:6443` and managed port-forward support, then recollect `native_service_port_mismatch_productcatalogservice` and `native_service_selector_mismatch_cartservice` first so packaged replay outputs include decisive Service/config evidence.
