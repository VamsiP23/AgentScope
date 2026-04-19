# Bounded ReAct vs DiagnosticAgent

Both runs use Claude Sonnet 4.0 on the same `native_48_strict_good` replay manifest.

## Headline

| Agent | Episodes | Exact | Grouped family | Action | Avg seconds | Avg tool/evidence calls |
|---|---:|---:|---:|---:|---:|---:|
| Bounded ReAct | 48 | 33/48 (68.8%) | 34/48 (70.8%) | 35/48 (72.9%) | 178.933 | 3.92 |
| DiagnosticAgent | 48 | 32/48 (66.7%) | 36/48 (75.0%) | 36/48 (75.0%) | 186.451 | 6.17 |

## Category Breakdown

| Category | Bounded exact/family/action | Diagnostic exact/family/action |
|---|---:|---:|
| availability_rollout | 12/17 / 12/17 / 13/17 | 13/17 / 13/17 / 13/17 |
| dependency_path_trace_centered | 1/10 / 2/10 / 1/10 | 2/10 / 6/10 / 6/10 |
| resource_performance | 10/11 / 10/11 / 11/11 | 7/11 / 7/11 / 7/11 |
| service_wiring_configuration | 10/10 / 10/10 / 10/10 | 10/10 / 10/10 / 10/10 |

## Family Breakdown

| Family | Bounded exact/family/action | Diagnostic exact/family/action |
|---|---:|---:|
| native_bad_env | 1/5 / 1/5 / 0/5 | 0/5 / 1/5 / 1/5 |
| native_bad_image_rollout | 5/5 / 5/5 / 5/5 | 5/5 / 5/5 / 5/5 |
| native_bad_probe_rollout | 4/5 / 4/5 / 4/5 | 5/5 / 5/5 / 5/5 |
| native_cpu_limit_throttle | 3/3 / 3/3 / 3/3 | 3/3 / 3/3 / 3/3 |
| native_cpu_pressure_stress_job | 3/3 / 3/3 / 3/3 | 0/3 / 0/3 / 0/3 |
| native_dependency_bad_endpoint | 0/5 / 1/5 / 1/5 | 2/5 / 5/5 / 5/5 |
| native_memory_limit_oom | 1/2 / 1/2 / 2/2 | 2/2 / 2/2 / 2/2 |
| native_memory_pressure_stress_job | 3/3 / 3/3 / 3/3 | 2/3 / 2/3 / 2/3 |
| native_pod_delete | 0/4 / 0/4 / 1/4 | 0/4 / 0/4 / 0/4 |
| native_scale_zero | 3/3 / 3/3 / 3/3 | 3/3 / 3/3 / 3/3 |
| native_service_port_mismatch | 5/5 / 5/5 / 5/5 | 5/5 / 5/5 / 5/5 |
| native_service_selector_mismatch | 5/5 / 5/5 / 5/5 | 5/5 / 5/5 / 5/5 |

## Changed Episode Outcomes

| Episode | Expected | Bounded submitted | Bounded E/F/A | Diagnostic submitted | Diagnostic E/F/A |
|---|---|---|---:|---|---:|
| native_bad_env_checkoutservice_email_004 | native_bad_env/rollout_undo | native_bad_probe_rollout/rollout_restart | False/False/False | native_bad_probe_rollout/rollout_undo | False/False/True |
| native_bad_env_checkoutservice_email_005 | native_bad_env/rollout_undo | native_bad_env/patch_resources | True/True/False | native_dependency_bad_endpoint/wait_and_monitor | False/True/False |
| native_bad_probe_cartservice_001 | native_bad_probe_rollout/rollout_undo | rollout_failure/rollout_undo | False/False/True | native_bad_probe_rollout/rollout_undo | True/True/True |
| native_bad_probe_cartservice_005 | native_bad_probe_rollout/rollout_undo | native_bad_probe_rollout/patch_resources | True/True/False | native_bad_probe/rollout_undo | True/True/True |
| native_cpu_pressure_stress_job_001 | native_cpu_pressure_stress_job/delete_stress_job | native_cpu_pressure_stress_job/delete_stress_job | True/True/True | native_bad_env/rollout_undo | False/False/False |
| native_cpu_pressure_stress_job_002 | native_cpu_pressure_stress_job/delete_stress_job | native_cpu_pressure_stress_job/delete_stress_job | True/True/True | native_dependency_bad_endpoint/ | False/False/False |
| native_cpu_pressure_stress_job_003 | native_cpu_pressure_stress_job/delete_stress_job | native_cpu_pressure_stress_job/delete_stress_job | True/True/True | native_dependency_bad_endpoint/wait_and_monitor | False/False/False |
| native_dependency_bad_endpoint_frontend_cartservice_003 | native_dependency_bad_endpoint/rollout_undo | native_memory_limit_oom/patch_resources | False/False/False | native_dependency_bad_endpoint/rollout_undo | True/True/True |
| native_dependency_bad_endpoint_frontend_cartservice_004 | native_dependency_bad_endpoint/rollout_undo | native_bad_probe_rollout/rollout_restart | False/False/False | native_dependency_bad_endpoint/rollout_undo | True/True/True |
| native_dependency_bad_endpoint_frontend_cartservice_005 | native_dependency_bad_endpoint/rollout_undo | native_dependency_bad_endpoint/rollout_restart | False/False/False | native_bad_env/rollout_undo | False/True/True |
| native_dependency_bad_endpoint_frontend_cartservice_006 | native_dependency_bad_endpoint/rollout_undo | native_bad_probe_rollout/rollout_undo | False/False/False | native_bad_env/rollout_undo | False/True/True |
| native_memory_limit_oom_cartservice_002 | native_memory_limit_oom/patch_resources | native_cpu_limit_throttle/patch_resources | False/False/True | native_memory_limit_oom/patch_resources | True/True/True |
| native_memory_pressure_stress_job_001 | native_memory_pressure_stress_job/delete_stress_job | native_memory_pressure_stress_job/delete_stress_job | True/True/True | native_dependency_bad_endpoint/restart_pod | False/False/False |
| native_pod_delete_cartservice_004 | native_pod_delete/wait_and_monitor | native_dependency_bad_endpoint/wait_and_monitor | False/False/True | native_bad_probe/rollout_undo | False/False/False |
