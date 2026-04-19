# Claude DiagnosticAgent Native48 Aggregate

Run root: `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/replay_runs/claude_diagnostic_compact_native48_20260419T081015Z`

## Headline

| Episodes | Exact | Grouped family | Action | Avg seconds |
|---:|---:|---:|---:|---:|
| 48 | 32/48 | 36/48 | 36/48 | 186.451 |

## Category

| Category | Episodes | Exact | Grouped family | Action | Avg seconds |
|---|---:|---:|---:|---:|---:|
| availability_rollout | 17 | 13/17 | 13/17 | 13/17 | 187.687 |
| dependency_path_trace_centered | 10 | 2/10 | 6/10 | 6/10 | 394.197 |
| resource_performance | 11 | 7/11 | 7/11 | 7/11 | 141.636 |
| service_wiring_configuration | 10 | 10/10 | 10/10 | 10/10 | 25.901 |

## Family

| Family | Episodes | Exact | Grouped family | Action |
|---|---:|---:|---:|---:|
| native_bad_env | 5 | 0/5 | 1/5 | 1/5 |
| native_bad_image_rollout | 5 | 5/5 | 5/5 | 5/5 |
| native_bad_probe_rollout | 5 | 5/5 | 5/5 | 5/5 |
| native_cpu_limit_throttle | 3 | 3/3 | 3/3 | 3/3 |
| native_cpu_pressure_stress_job | 3 | 0/3 | 0/3 | 0/3 |
| native_dependency_bad_endpoint | 5 | 2/5 | 5/5 | 5/5 |
| native_memory_limit_oom | 2 | 2/2 | 2/2 | 2/2 |
| native_memory_pressure_stress_job | 3 | 2/3 | 2/3 | 2/3 |
| native_pod_delete | 4 | 0/4 | 0/4 | 0/4 |
| native_scale_zero | 3 | 3/3 | 3/3 | 3/3 |
| native_service_port_mismatch | 5 | 5/5 | 5/5 | 5/5 |
| native_service_selector_mismatch | 5 | 5/5 | 5/5 | 5/5 |

## Failures / Partials

| Episode | Expected | Submitted | Exact | Family | Action |
|---|---|---|---:|---:|---:|
| native_pod_delete_cartservice_001 | native_pod_delete/wait_and_monitor | native_bad_probe_rollout/rollout_undo | False | False | False |
| native_pod_delete_cartservice_002 | native_pod_delete/wait_and_monitor | native_bad_probe/rollout_undo | False | False | False |
| native_pod_delete_cartservice_004 | native_pod_delete/wait_and_monitor | native_bad_probe/rollout_undo | False | False | False |
| native_pod_delete_cartservice_005 | native_pod_delete/wait_and_monitor | native_bad_probe_rollout/rollout_undo | False | False | False |
| native_dependency_bad_endpoint_frontend_cartservice_002 | native_dependency_bad_endpoint/rollout_undo | native_bad_env/rollout_undo | False | True | True |
| native_dependency_bad_endpoint_frontend_cartservice_005 | native_dependency_bad_endpoint/rollout_undo | native_bad_env/rollout_undo | False | True | True |
| native_dependency_bad_endpoint_frontend_cartservice_006 | native_dependency_bad_endpoint/rollout_undo | native_bad_env/rollout_undo | False | True | True |
| native_bad_env_checkoutservice_email_001 | native_bad_env/rollout_undo | native_cpu_limit_throttle/patch_resources | False | False | False |
| native_bad_env_checkoutservice_email_002 | native_bad_env/rollout_undo | native_pod_delete/wait_and_monitor | False | False | False |
| native_bad_env_checkoutservice_email_003 | native_bad_env/rollout_undo | native_service_port_mismatch/patch_service_target_port | False | False | False |
| native_bad_env_checkoutservice_email_004 | native_bad_env/rollout_undo | native_bad_probe_rollout/rollout_undo | False | False | True |
| native_bad_env_checkoutservice_email_005 | native_bad_env/rollout_undo | native_dependency_bad_endpoint/wait_and_monitor | False | True | False |
| native_cpu_pressure_stress_job_001 | native_cpu_pressure_stress_job/delete_stress_job | native_bad_env/rollout_undo | False | False | False |
| native_cpu_pressure_stress_job_002 | native_cpu_pressure_stress_job/delete_stress_job | native_dependency_bad_endpoint/ | False | False | False |
| native_cpu_pressure_stress_job_003 | native_cpu_pressure_stress_job/delete_stress_job | native_dependency_bad_endpoint/wait_and_monitor | False | False | False |
| native_memory_pressure_stress_job_001 | native_memory_pressure_stress_job/delete_stress_job | native_dependency_bad_endpoint/restart_pod | False | False | False |
