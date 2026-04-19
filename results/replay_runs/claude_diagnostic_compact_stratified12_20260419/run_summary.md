# Claude DiagnosticAgent Compact Stratified12

- Run root: `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/replay_runs/claude_diagnostic_compact_stratified12_20260419`
- Evaluated: 12/12
- Exact: 7/12
- Family: 8/12
- Action: 9/12
- Average elapsed seconds: 37.101

| # | Episode | Exact | Family | Action | Seconds | Submitted | Expected |
|---:|---|---:|---:|---:|---:|---|---|
| 1 | `native_service_port_mismatch_productcatalogservice_001` | True | True | True | 24.029 | `native_service_port_mismatch/patch_service_target_port` | `native_service_port_mismatch/patch_service_target_port` |
| 2 | `native_service_selector_mismatch_cartservice_001` | True | True | True | 20.655 | `native_service_selector_mismatch/patch_service_selector` | `native_service_selector_mismatch/patch_service_selector` |
| 3 | `native_bad_image_productcatalogservice_001` | True | True | True | 27.216 | `native_bad_image_rollout/rollout_undo` | `native_bad_image_rollout/rollout_undo` |
| 4 | `native_bad_probe_cartservice_001` | True | True | True | 30.184 | `native_bad_probe_rollout/rollout_undo` | `native_bad_probe_rollout/rollout_undo` |
| 5 | `native_scale_zero_recommendationservice_001` | True | True | True | 25.059 | `native_scale_zero/scale_deployment` | `native_scale_zero/scale_deployment` |
| 6 | `native_pod_delete_cartservice_001` | False | False | False | 30.332 | `native_bad_probe_rollout/rollout_undo` | `native_pod_delete/wait_and_monitor` |
| 7 | `native_dependency_bad_endpoint_frontend_cartservice_002` | False | True | True | 35.59 | `native_bad_env/rollout_undo` | `native_dependency_bad_endpoint/rollout_undo` |
| 8 | `native_bad_env_checkoutservice_email_001` | False | False | False | 29.22 | `native_cpu_limit_throttle/patch_resources` | `native_bad_env/rollout_undo` |
| 9 | `native_cpu_limit_throttle_checkoutservice_001` | True | True | True | 26.644 | `native_cpu_limit_throttle/patch_resources` | `native_cpu_limit_throttle/patch_resources` |
| 10 | `native_memory_limit_oom_cartservice_002` | False | False | True | 33.048 | `native_cpu_limit_throttle/patch_resources` | `native_memory_limit_oom/patch_resources` |
| 11 | `native_cpu_pressure_stress_job_001` | True | True | True | 129.709 | `native_cpu_pressure_stress_job/delete_stress_job` | `native_cpu_pressure_stress_job/delete_stress_job` |
| 12 | `native_memory_pressure_stress_job_001` | False | False | False | 33.527 | `native_dependency_bad_endpoint/wait_and_monitor` | `native_memory_pressure_stress_job/delete_stress_job` |
