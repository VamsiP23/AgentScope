# Claude DiagnosticAgent Compact Smoke5

- Run root: `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/replay_runs/claude_diagnostic_compact_smoke5_20260419`
- Evaluated: 5/5
- Exact: 4/5
- Family: 4/5
- Action: 4/5

| # | Episode | Exact | Family | Action | Seconds | Submitted | Expected |
|---:|---|---:|---:|---:|---:|---|---|
| 1 | `native_service_port_mismatch_productcatalogservice_001` | True | True | True | 28.321 | `native_service_port_mismatch/patch_service_target_port` | `native_service_port_mismatch/patch_service_target_port` |
| 2 | `native_bad_image_productcatalogservice_001` | True | True | True | 29.824 | `native_bad_image_rollout/rollout_undo` | `native_bad_image_rollout/rollout_undo` |
| 3 | `native_pod_delete_cartservice_001` | False | False | False | 28.424 | `native_bad_probe/rollout_undo` | `native_pod_delete/wait_and_monitor` |
| 4 | `native_dependency_bad_endpoint_frontend_cartservice_002` | True | True | True | 30.654 | `native_dependency_bad_endpoint/rollout_undo` | `native_dependency_bad_endpoint/rollout_undo` |
| 5 | `native_cpu_pressure_stress_job_001` | True | True | True | 33.082 | `native_cpu_pressure_stress_job/delete_stress_job` | `native_cpu_pressure_stress_job/delete_stress_job` |
