# Native episode collection summary

Run: `automation_20260416T080518Z`

Status: blocked before live collection.

No packaged episode was counted in this run. The observability preflight failed for Prometheus, Jaeger, and frontend local access, and follow-up `kubectl port-forward` / Python subprocess `kubectl` calls were blocked by the sandbox network policy with:

`Unable to connect to the server: dial tcp 127.0.0.1:6443: connect: operation not permitted`

## Completed

- Enriched `get_k8s_state(service)` with agent-callable Kubernetes Service/config evidence: Service selector, ports/targetPorts, selected pods, deployment pods, pod labels, container ports, Endpoints, EndpointSlices, and ready/not-ready endpoint counts.
- Preserved the new Service/config evidence in `scripts/capture_episode_dataset.py` packaged replay outputs.
- Added benchmark-suite mappings for the seven requested medium native scenarios.
- Added structured `delete_stress_job` action scoring for native CPU/memory stress-job scenarios.
- Ran `py_compile` successfully on the touched Python modules.
- Loaded all five easy and seven medium native benchmark problem IDs successfully.

## Not Counted

- `native_service_port_mismatch_productcatalogservice_001` remains evidence-insufficient. Its initial context is non-leaky, but replay-visible `get_k8s_state(productcatalogservice)` does not contain the decisive Service targetPort/container port evidence because it was packaged before this run's evidence-layer patch. Its packaged action ground truth was also stale.
- `native_scale_zero_recommendationservice_001` was not revalidated or counted in this run.

## Scenario Counts

All requested scenarios remain at `0/3` counted episodes for this run. Medium mappings are now present for:

- `native_pod_delete_cartservice`
- `native_dependency_bad_endpoint_frontend_cartservice`
- `native_cpu_limit_throttle_checkoutservice`
- `native_memory_limit_oom_cartservice`
- `native_cpu_pressure_stress_job`
- `native_memory_pressure_stress_job`
- `native_bad_env_checkoutservice_email`

## Next Step

Run the native evidence probes from an environment where `kubectl port-forward` and Python subprocess `kubectl` access are permitted. Start by recollecting `native_service_port_mismatch_productcatalogservice` and `native_service_selector_mismatch_cartservice`, then audit that replay `get_k8s_state(...)` exposes the decisive Service selector/targetPort evidence before counting any package.
