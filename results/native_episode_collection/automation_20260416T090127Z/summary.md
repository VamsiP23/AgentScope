# Native Episode Collection Run

- Run ID: `automation_20260416T090127Z`
- Status: blocked before live collection
- Newly collected packaged episodes: 0
- Counted benchmark-ready episodes: 0

## Blocker

`scripts/repair_observability_access.py --namespace default` failed for Prometheus, Jaeger, and frontend local access. The managed port-forward logs show `kubectl port-forward` failing with:

```text
Unable to connect to the server: dial tcp 127.0.0.1:6443: connect: operation not permitted
```

Direct `kubectl get pods -n default` succeeded and showed the app plus observability pods running, but foreground `kubectl port-forward -n default svc/prometheus 9090:9090` failed with the same sandbox/network-policy denial. Because evidence probes and full-evidence collection need Prometheus/Jaeger/frontend access, no live fault was applied and no episode was promoted.

## Preflight Results

- Memory was read and the workspace was preserved.
- No destructive cleanup commands were used.
- Native easy and medium suite mappings are present and their experiment files exist.
- The two pinned hard scenario IDs are not implemented yet.
- `py_compile` passed for the benchmark/replay/capture/evidence modules checked this run.
- Existing native packages remain uncounted until recollected or replay-audited after the Service/config evidence patch.

## Scenario Counts

All requested easy, medium, and hard scenarios are below the target of 3 packaged episodes because live collection was blocked before any experiment could be run. The hard scenarios also still need implementation.

## Existing Packages Not Counted

- `/Users/aarnavsawant/Documents/CS6365/AgentScope/datasets/episodes/native_service_port_mismatch_productcatalogservice/native_service_port_mismatch_productcatalogservice_001.json`: non-leaky initial context, but it was packaged before the current Service/config replay evidence fix and needs recollection/regeneration plus replay audit.
- `/Users/aarnavsawant/Documents/CS6365/AgentScope/datasets/episodes/native_scale_zero_recommendationservice/native_scale_zero_recommendationservice_001.json`: not revalidated during this blocked run.

## Cleanup

No new native fault was applied during this run. Direct pod check showed the default namespace workloads running; no post-fault cleanup was needed.

## Next Step

Rerun from an environment where `kubectl port-forward` is permitted. Start with `native_service_port_mismatch_productcatalogservice` and `native_service_selector_mismatch_cartservice`, then audit replay `get_k8s_state(...)` for decisive Service selector/targetPort evidence before counting any package.
