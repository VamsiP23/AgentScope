# Claude Generic ReAct Native48

- Run root: `<repo-root>/results/replay_runs/claude_generic_react_compact_native48_20260419T164113Z`
- Generated: 2026-04-19T19:11:47Z

## Headline

| Episodes | Exact | Grouped family | Action | Avg seconds | Avg tool calls | Avg repeated calls |
|---:|---:|---:|---:|---:|---:|---:|
| 48 | 27/48 (56.2%) | 27/48 (56.2%) | 26/48 (54.2%) | 142.27 | 3.5 | 0.0 |

## Category Breakdown

| Category | Episodes | Exact | Grouped family | Action | Avg seconds |
|---|---:|---:|---:|---:|---:|
| availability_rollout | 17 | 12/17 (70.6%) | 12/17 (70.6%) | 10/17 (58.8%) | 119.024 |
| dependency_path_trace_centered | 10 | 0/10 (0.0%) | 0/10 (0.0%) | 1/10 (10.0%) | 187.601 |
| resource_performance | 11 | 5/11 (45.5%) | 5/11 (45.5%) | 5/11 (45.5%) | 182.727 |
| service_wiring_configuration | 10 | 10/10 (100.0%) | 10/10 (100.0%) | 10/10 (100.0%) | 91.956 |

## Family Breakdown

| Family | Episodes | Exact | Grouped family | Action | Avg seconds |
|---|---:|---:|---:|---:|---:|
| native_bad_env | 5 | 0/5 (0.0%) | 0/5 (0.0%) | 1/5 (20.0%) | 170.038 |
| native_bad_image_rollout | 5 | 5/5 (100.0%) | 5/5 (100.0%) | 5/5 (100.0%) | 84.301 |
| native_bad_probe_rollout | 5 | 4/5 (80.0%) | 4/5 (80.0%) | 2/5 (40.0%) | 130.678 |
| native_cpu_limit_throttle | 3 | 3/3 (100.0%) | 3/3 (100.0%) | 3/3 (100.0%) | 116.89 |
| native_cpu_pressure_stress_job | 3 | 0/3 (0.0%) | 0/3 (0.0%) | 0/3 (0.0%) | 237.019 |
| native_dependency_bad_endpoint | 5 | 0/5 (0.0%) | 0/5 (0.0%) | 0/5 (0.0%) | 205.163 |
| native_memory_limit_oom | 2 | 2/2 (100.0%) | 2/2 (100.0%) | 2/2 (100.0%) | 115.56 |
| native_memory_pressure_stress_job | 3 | 0/3 (0.0%) | 0/3 (0.0%) | 0/3 (0.0%) | 239.051 |
| native_pod_delete | 4 | 0/4 (0.0%) | 0/4 (0.0%) | 0/4 (0.0%) | 161.103 |
| native_scale_zero | 3 | 3/3 (100.0%) | 3/3 (100.0%) | 3/3 (100.0%) | 101.367 |
| native_service_port_mismatch | 5 | 5/5 (100.0%) | 5/5 (100.0%) | 5/5 (100.0%) | 86.835 |
| native_service_selector_mismatch | 5 | 5/5 (100.0%) | 5/5 (100.0%) | 5/5 (100.0%) | 97.077 |

## Misses

| Episode | Category | Expected | Submitted | E/F/A | Seconds |
|---|---|---|---|---:|---:|
| native_bad_probe_cartservice_001 | availability_rollout | native_bad_probe_rollout/rollout_undo | native_dependency_bad_endpoint/rollout_restart | False/False/False | 186.339 |
| native_bad_probe_cartservice_004 | availability_rollout | native_bad_probe_rollout/rollout_undo | native_bad_probe_rollout/patch_resources | True/True/False | 117.044 |
| native_bad_probe_cartservice_005 | availability_rollout | native_bad_probe_rollout/rollout_undo | native_bad_probe_rollout/patch_resources | True/True/False | 116.725 |
| native_pod_delete_cartservice_001 | availability_rollout | native_pod_delete/wait_and_monitor | native_bad_probe_rollout/rollout_undo | False/False/False | 187.672 |
| native_pod_delete_cartservice_002 | availability_rollout | native_pod_delete/wait_and_monitor | native_bad_probe_rollout/restart_pod | False/False/False | 148.454 |
| native_pod_delete_cartservice_004 | availability_rollout | native_pod_delete/wait_and_monitor | rollout_failure/rollout_undo | False/False/False | 149.553 |
| native_pod_delete_cartservice_005 | availability_rollout | native_pod_delete/wait_and_monitor | dependency_localization/rollout_restart | False/False/False | 158.735 |
| native_dependency_bad_endpoint_frontend_cartservice_002 | dependency_path_trace_centered | native_dependency_bad_endpoint/rollout_undo | runtime_failure/wait_and_monitor | False/False/False | 223.729 |
| native_dependency_bad_endpoint_frontend_cartservice_003 | dependency_path_trace_centered | native_dependency_bad_endpoint/rollout_undo | partial_degradation/rollout_restart | False/False/False | 191.422 |
| native_dependency_bad_endpoint_frontend_cartservice_004 | dependency_path_trace_centered | native_dependency_bad_endpoint/rollout_undo | runtime_failure/rollout_restart | False/False/False | 237.944 |
| native_dependency_bad_endpoint_frontend_cartservice_005 | dependency_path_trace_centered | native_dependency_bad_endpoint/rollout_undo | native_bad_probe_rollout/rollout_restart | False/False/False | 241.365 |
| native_dependency_bad_endpoint_frontend_cartservice_006 | dependency_path_trace_centered | native_dependency_bad_endpoint/rollout_undo | native_bad_probe_rollout/rollout_undo | False/False/False | 131.353 |
| native_bad_env_checkoutservice_email_001 | dependency_path_trace_centered | native_bad_env/rollout_undo | native_cpu_limit_throttle/patch_resources | False/False/False | 124.59 |
| native_bad_env_checkoutservice_email_002 | dependency_path_trace_centered | native_bad_env/rollout_undo | pod_disturbance/rollout_restart | False/False/False | 236.422 |
| native_bad_env_checkoutservice_email_003 | dependency_path_trace_centered | native_bad_env/rollout_undo | native_service_port_mismatch/patch_service_target_port | False/False/False | 194.838 |
| native_bad_env_checkoutservice_email_004 | dependency_path_trace_centered | native_bad_env/rollout_undo | native_bad_probe_rollout/rollout_undo | False/False/True | 169.288 |
| native_bad_env_checkoutservice_email_005 | dependency_path_trace_centered | native_bad_env/rollout_undo | native_service_port_mismatch/patch_service_target_port | False/False/False | 125.054 |
| native_cpu_pressure_stress_job_001 | resource_performance | native_cpu_pressure_stress_job/delete_stress_job | runtime_failure/wait_and_monitor | False/False/False | 250.047 |
| native_cpu_pressure_stress_job_002 | resource_performance | native_cpu_pressure_stress_job/delete_stress_job | runtime_failure/wait_and_monitor | False/False/False | 230.994 |
| native_cpu_pressure_stress_job_003 | resource_performance | native_cpu_pressure_stress_job/delete_stress_job | pod_disturbance/rollout_restart | False/False/False | 230.015 |
| native_memory_pressure_stress_job_001 | resource_performance | native_memory_pressure_stress_job/delete_stress_job | dependency_localization/wait_and_monitor | False/False/False | 283.322 |
| native_memory_pressure_stress_job_002 | resource_performance | native_memory_pressure_stress_job/delete_stress_job | runtime_failure/wait_and_monitor | False/False/False | 242.597 |
| native_memory_pressure_stress_job_003 | resource_performance | native_memory_pressure_stress_job/delete_stress_job | native_cpu_limit_throttle/patch_resources | False/False/False | 191.235 |
