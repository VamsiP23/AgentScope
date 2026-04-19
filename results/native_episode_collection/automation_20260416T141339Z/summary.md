# Native Episode Collection Automation - 20260416T141339Z

Result: 0 new packaged episodes collected; 0 benchmark-ready episodes counted.

## Preflight
- Memory read and existing dirty workspace state preserved; no destructive cleanup used.
- py_compile passed for capture/replay/evaluator/ReAct/Kubernetes/evidence-probe/observability/native modules.
- Easy and medium native mappings are present and mapped experiment files exist.
- Pinned hard scenario mappings/backend implementation are still missing.

## Blocker
- `scripts/repair_observability_access.py --namespace default` failed for Prometheus, Jaeger, and frontend localhost access.
- Port-forward/API failure detail: `Unable to connect to the server: dial tcp 127.0.0.1:6443: connect: operation not permitted`.
- `kubectl get pods -n default --no-headers` succeeded once and showed workloads/observability pods Running, but native-fault cleanup verification failed with the same API denial.

## Collection Counts
- `native_service_port_mismatch_productcatalogservice`: 0/3 collected; blocked before fault application by observability/API access failure.
- `native_service_selector_mismatch_cartservice`: 0/3 collected; blocked before fault application by observability/API access failure.
- `native_bad_image_productcatalogservice`: 0/3 collected; blocked before fault application by observability/API access failure.
- `native_bad_probe_cartservice`: 0/3 collected; blocked before fault application by observability/API access failure.
- `native_scale_zero_recommendationservice`: 0/3 collected; blocked before fault application by observability/API access failure.
- `native_pod_delete_cartservice`: 0/3 collected; blocked before fault application by observability/API access failure.
- `native_dependency_bad_endpoint_frontend_cartservice`: 0/3 collected; blocked before fault application by observability/API access failure.
- `native_cpu_limit_throttle_checkoutservice`: 0/3 collected; blocked before fault application by observability/API access failure.
- `native_memory_limit_oom_cartservice`: 0/3 collected; blocked before fault application by observability/API access failure.
- `native_cpu_pressure_stress_job`: 0/3 collected; blocked before fault application by observability/API access failure.
- `native_memory_pressure_stress_job`: 0/3 collected; blocked before fault application by observability/API access failure.
- `native_bad_env_checkoutservice_email`: 0/3 collected; blocked before fault application by observability/API access failure.
- `native_noisy_rollout_plus_service_port_mismatch_productcatalogservice`: 0/3 collected; blocked before fault application by observability/API access failure.
- `native_trace_dependency_bad_endpoint_frontend_cartservice`: 0/3 collected; blocked before fault application by observability/API access failure.

## Existing Packages
- `native_service_port_mismatch_productcatalogservice_001`: clean initial context; replay package lacks Service/config evidence; not counted.
- `native_scale_zero_recommendationservice_001`: clean initial context; not freshly revalidated under live-access blocker; not counted.

## Cleanup
- No native fault was applied in this run.
- Cleanup verification query was blocked by the Kubernetes API permission error; no destructive cleanup was attempted.

## Next Step
- Rerun from a context where `kubectl port-forward` and API reads are permitted, then recollect the two Service/config easy scenarios first and audit replay-visible Service selector/targetPort evidence before counting any package.
