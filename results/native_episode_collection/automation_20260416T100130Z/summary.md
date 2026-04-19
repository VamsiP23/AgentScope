# Native Episode Collection Summary

- Run: `automation_20260416T100130Z`
- Started: `2026-04-16T10:01:30Z`
- Workspace: `/Users/aarnavsawant/Documents/CS6365/AgentScope`
- Status: blocked before collection

## Outcome

No new packaged dataset episodes were collected or counted. No native fault was applied.

The run stopped at the observability gate because `scripts/repair_observability_access.py --namespace default` could not establish local access to Prometheus, Jaeger, or frontend. The managed port-forward logs show repeated failures:

```text
Unable to connect to the server: dial tcp 127.0.0.1:6443: connect: operation not permitted
```

Direct `kubectl get pods -n default` briefly succeeded and showed the default namespace workloads running, but subsequent `kubectl` service/deployment checks were denied by the same sandbox/API-server access error. Because the evidence probe and replay packages depend on those live evidence paths, collecting episodes would not satisfy the benchmark-validity gate.

## Preflight

- Memory was read.
- Existing workspace changes were preserved; no destructive cleanup commands were used.
- `py_compile` passed for the checked benchmark/replay/capture/evidence modules.
- Easy and medium native benchmark-suite mappings are present and their experiment files exist.
- The two pinned hard scenario IDs are still missing mappings/backend implementation.
- Structured submit fields, fixed-label evaluator behavior, diagnosis-only replay mode, auto-increment capture output, non-leaky initial-context generation, and Service/config evidence enrichment are present in the main workspace.

## Counts

| Scenario | Target | Collected | Reason |
| --- | ---: | ---: | --- |
| `native_service_port_mismatch_productcatalogservice` | 3 | 0 | Observability repair failed before fault apply/probe |
| `native_service_selector_mismatch_cartservice` | 3 | 0 | Observability repair failed before fault apply/probe |
| `native_bad_image_productcatalogservice` | 3 | 0 | Observability repair failed before fault apply/probe |
| `native_bad_probe_cartservice` | 3 | 0 | Observability repair failed before fault apply/probe |
| `native_scale_zero_recommendationservice` | 3 | 0 | Observability repair failed before fault apply/probe |
| `native_pod_delete_cartservice` | 3 | 0 | Observability repair failed before fault apply/probe |
| `native_dependency_bad_endpoint_frontend_cartservice` | 3 | 0 | Observability repair failed before fault apply/probe |
| `native_cpu_limit_throttle_checkoutservice` | 3 | 0 | Observability repair failed before fault apply/probe |
| `native_memory_limit_oom_cartservice` | 3 | 0 | Observability repair failed before fault apply/probe |
| `native_cpu_pressure_stress_job` | 3 | 0 | Observability repair failed before fault apply/probe |
| `native_memory_pressure_stress_job` | 3 | 0 | Observability repair failed before fault apply/probe |
| `native_bad_env_checkoutservice_email` | 3 | 0 | Observability repair failed before fault apply/probe |
| `native_noisy_rollout_plus_service_port_mismatch_productcatalogservice` | 3 | 0 | Hard mapping/backend still missing |
| `native_trace_dependency_bad_endpoint_frontend_cartservice` | 3 | 0 | Hard mapping/backend still missing |

## Existing Packages

- `/Users/aarnavsawant/Documents/CS6365/AgentScope/datasets/episodes/native_service_port_mismatch_productcatalogservice/native_service_port_mismatch_productcatalogservice_001.json`: not counted. Initial context is non-leaky, but the package was not freshly regenerated/replay-validated after the Service/config evidence-layer fix.
- `/Users/aarnavsawant/Documents/CS6365/AgentScope/datasets/episodes/native_scale_zero_recommendationservice/native_scale_zero_recommendationservice_001.json`: not counted. Initial context is non-leaky, but this run could not replay-validate or audit it.

## Evidence Coverage

No new evidence bundle was collected. Coverage is therefore unavailable for Kubernetes workload state, Service/config state, logs, metrics, traces/dependency traces, detector metadata, and traffic/fault logs. Cleanup status is clean in the narrow sense that no native fault was applied during this run; live cleanup verification was blocked by later `kubectl` API denial.

## Artifacts

- Summary JSON: `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/native_episode_collection/automation_20260416T100130Z/summary.json`
- Summary Markdown: `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/native_episode_collection/automation_20260416T100130Z/summary.md`
- Prometheus port-forward log: `/Users/aarnavsawant/Documents/CS6365/AgentScope/.runtime/port_forwards/prometheus.log`
- Jaeger port-forward log: `/Users/aarnavsawant/Documents/CS6365/AgentScope/.runtime/port_forwards/jaeger.log`
- Frontend port-forward log: `/Users/aarnavsawant/Documents/CS6365/AgentScope/.runtime/port_forwards/frontend-external.log`

## Next Step

Rerun from an environment where `kubectl port-forward` and Python subprocess `kubectl` calls are permitted. Recollect `native_service_port_mismatch_productcatalogservice` and `native_service_selector_mismatch_cartservice` first, then audit replay `get_k8s_state(...)` for decisive Service selector/targetPort evidence before counting any package.
