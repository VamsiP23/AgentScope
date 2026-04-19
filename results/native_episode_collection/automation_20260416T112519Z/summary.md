# Native Collection Run: 2026-04-16T11:25:19Z

Result: 0 new packaged episodes collected and 0 benchmark-ready episodes counted.

## Preflight

- Memory read: yes.
- Destructive cleanup used: no.
- Python compile checks: passed for capture, replay, evaluator, ReAct, and Kubernetes evidence modules.
- Easy and medium native mappings: present; all mapped experiment files exist.
- Pinned hard mappings still missing:
  - `native_noisy_rollout_plus_service_port_mismatch_productcatalogservice`
  - `native_trace_dependency_bad_endpoint_frontend_cartservice`
- Service/config evidence layer: present in code, but existing packages were captured before this evidence was included in replay outputs.

## Blocker

`python3 scripts/repair_observability_access.py --namespace default` failed:

- Prometheus: local access at `http://localhost:9090` is not reachable after refreshing the managed forward.
- Jaeger: local access at `http://localhost:16686` is not reachable after refreshing the managed forward.
- Frontend: local access at `http://localhost:8080` is not reachable after refreshing the managed forward.

Direct Kubernetes access is also denied from this sandbox:

```text
Unable to connect to the server: dial tcp 127.0.0.1:6443: connect: operation not permitted
```

Because live evidence probes require Kubernetes API access, no fault was applied and no cleanup mutation was attempted.

## Existing Package Status

- `/Users/aarnavsawant/Documents/CS6365/AgentScope/datasets/episodes/native_service_port_mismatch_productcatalogservice/native_service_port_mismatch_productcatalogservice_001.json`
  - Replay load: passed.
  - Initial context: non-leaky.
  - Counted: no.
  - Reason: decisive Service targetPort evidence is absent from replay `get_k8s_state(...)` output because this package predates the Service/config evidence patch.
- `/Users/aarnavsawant/Documents/CS6365/AgentScope/datasets/episodes/native_scale_zero_recommendationservice/native_scale_zero_recommendationservice_001.json`
  - Replay load: passed.
  - Initial context: non-leaky.
  - Counted: no.
  - Reason: not freshly regenerated, audited, or replay-validated during this run due to the Kubernetes access blocker.

## Scenario Counts

Every requested easy and medium scenario remains at `0 / 3` collected for this run. The hard scenarios remain at `0 / 3` because their mappings/backend implementation are still missing and live collection is blocked.

## Cleanup

No native fault was applied in this run. Cleanup status could not be verified from this sandbox because `kubectl` cannot reach the cluster API.

## Next Step

Rerun from an environment where `kubectl` can reach `https://127.0.0.1:6443` and port-forward is permitted. Collect `native_service_port_mismatch_productcatalogservice` and `native_service_selector_mismatch_cartservice` first, then audit replay `get_k8s_state(...)` for Service selector, ports/targetPorts, pod labels, and endpoint readiness before counting any package.
