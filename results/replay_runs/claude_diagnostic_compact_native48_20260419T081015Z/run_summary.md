# Claude DiagnosticAgent Native48

- Status: `complete`
- Run root: `<repo-root>/results/replay_runs/claude_diagnostic_compact_native48_20260419T081015Z`
- Completed evaluations: 48/48
- Exact: 32/48
- Grouped family: 36/48
- Action: 36/48

| # | Episode | Status | Exact | Family | Action | Submitted | Expected | Seconds |
|---:|---|---|---:|---:|---:|---|---|---:|
| 1 | native_service_port_mismatch_productcatalogservice_001 | ok | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port | 27.863 |
| 2 | native_service_port_mismatch_productcatalogservice_002 | ok | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port | 26.963 |
| 3 | native_service_port_mismatch_productcatalogservice_003 | ok | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port | 26.19 |
| 4 | native_service_port_mismatch_productcatalogservice_004 | ok | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port | 27.445 |
| 5 | native_service_port_mismatch_productcatalogservice_005 | ok | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port | 33.134 |
| 6 | native_service_selector_mismatch_cartservice_001 | ok | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector | 23.336 |
| 7 | native_service_selector_mismatch_cartservice_002 | ok | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector | 23.944 |
| 8 | native_service_selector_mismatch_cartservice_003 | ok | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector | 23.265 |
| 9 | native_service_selector_mismatch_cartservice_004 | ok | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector | 23.403 |
| 10 | native_service_selector_mismatch_cartservice_005 | ok | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector | 23.466 |
| 11 | native_bad_image_productcatalogservice_001 | ok | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo | 32.314 |
| 12 | native_bad_image_productcatalogservice_002 | ok | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo | 29.68 |
| 13 | native_bad_image_productcatalogservice_003 | ok | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo | 29.489 |
| 14 | native_bad_image_productcatalogservice_005 | ok | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo | 30.698 |
| 15 | native_bad_image_productcatalogservice_006 | ok | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo | 28.34 |
| 16 | native_bad_probe_cartservice_001 | ok | True | True | True | native_bad_probe_rollout/rollout_undo | native_bad_probe_rollout/rollout_undo | 28.742 |
| 17 | native_bad_probe_cartservice_002 | ok | True | True | True | native_bad_probe_rollout/rollout_undo | native_bad_probe_rollout/rollout_undo | 26.74 |
| 18 | native_bad_probe_cartservice_003 | ok | True | True | True | native_bad_probe_rollout/rollout_undo | native_bad_probe_rollout/rollout_undo | 30.059 |
| 19 | native_bad_probe_cartservice_004 | ok | True | True | True | native_bad_probe_rollout/rollout_undo | native_bad_probe_rollout/rollout_undo | 607.116 |
| 20 | native_bad_probe_cartservice_005 | ok | True | True | True | native_bad_probe/rollout_undo | native_bad_probe_rollout/rollout_undo | 189.429 |
| 21 | native_scale_zero_recommendationservice_001 | ok | True | True | True | native_scale_zero/scale_deployment | native_scale_zero/scale_deployment | 25.3 |
| 22 | native_scale_zero_recommendationservice_002 | ok | True | True | True | native_scale_zero/scale_deployment | native_scale_zero/scale_deployment | 23.663 |
| 23 | native_scale_zero_recommendationservice_004 | ok | True | True | True | native_scale_zero/scale_deployment | native_scale_zero/scale_deployment | 24.675 |
| 24 | native_pod_delete_cartservice_001 | ok | False | False | False | native_bad_probe_rollout/rollout_undo | native_pod_delete/wait_and_monitor | 29.188 |
| 25 | native_pod_delete_cartservice_002 | ok | False | False | False | native_bad_probe/rollout_undo | native_pod_delete/wait_and_monitor | 962.879 |
| 26 | native_pod_delete_cartservice_004 | ok | False | False | False | native_bad_probe/rollout_undo | native_pod_delete/wait_and_monitor | 1062.089 |
| 27 | native_pod_delete_cartservice_005 | ok | False | False | False | native_bad_probe_rollout/rollout_undo | native_pod_delete/wait_and_monitor | 30.283 |
| 28 | native_dependency_bad_endpoint_frontend_cartservice_002 | ok | False | True | True | native_bad_env/rollout_undo | native_dependency_bad_endpoint/rollout_undo | 34.405 |
| 29 | native_dependency_bad_endpoint_frontend_cartservice_003 | ok | True | True | True | native_dependency_bad_endpoint/rollout_undo | native_dependency_bad_endpoint/rollout_undo | 955.76 |
| 30 | native_dependency_bad_endpoint_frontend_cartservice_004 | ok | True | True | True | native_dependency_bad_endpoint/rollout_undo | native_dependency_bad_endpoint/rollout_undo | 29.098 |
| 31 | native_dependency_bad_endpoint_frontend_cartservice_005 | ok | False | True | True | native_bad_env/rollout_undo | native_dependency_bad_endpoint/rollout_undo | 1087.89 |
| 32 | native_dependency_bad_endpoint_frontend_cartservice_006 | ok | False | True | True | native_bad_env/rollout_undo | native_dependency_bad_endpoint/rollout_undo | 30.606 |
| 33 | native_bad_env_checkoutservice_email_001 | ok | False | False | False | native_cpu_limit_throttle/patch_resources | native_bad_env/rollout_undo | 31.206 |
| 34 | native_bad_env_checkoutservice_email_002 | ok | False | False | False | native_pod_delete/wait_and_monitor | native_bad_env/rollout_undo | 708.868 |
| 35 | native_bad_env_checkoutservice_email_003 | ok | False | False | False | native_service_port_mismatch/patch_service_target_port | native_bad_env/rollout_undo | 44.061 |
| 36 | native_bad_env_checkoutservice_email_004 | ok | False | False | True | native_bad_probe_rollout/rollout_undo | native_bad_env/rollout_undo | 29.556 |
| 37 | native_bad_env_checkoutservice_email_005 | ok | False | True | False | native_dependency_bad_endpoint/wait_and_monitor | native_bad_env/rollout_undo | 990.519 |
| 38 | native_cpu_limit_throttle_checkoutservice_001 | ok | True | True | True | native_cpu_limit_throttle/patch_resources | native_cpu_limit_throttle/patch_resources | 24.633 |
| 39 | native_cpu_limit_throttle_checkoutservice_002 | ok | True | True | True | native_cpu_limit_throttle/patch_resources | native_cpu_limit_throttle/patch_resources | 30.63 |
| 40 | native_cpu_limit_throttle_checkoutservice_003 | ok | True | True | True | native_cpu_limit_throttle/patch_resources | native_cpu_limit_throttle/patch_resources | 23.85 |
| 41 | native_memory_limit_oom_cartservice_002 | ok | True | True | True | native_memory_limit_oom/patch_resources | native_memory_limit_oom/patch_resources | 1078.332 |
| 42 | native_memory_limit_oom_cartservice_003 | ok | True | True | True | native_memory_limit_oom/patch_resources | native_memory_limit_oom/patch_resources | 40.377 |
| 43 | native_cpu_pressure_stress_job_001 | ok | False | False | False | native_bad_env/rollout_undo | native_cpu_pressure_stress_job/delete_stress_job | 33.508 |
| 44 | native_cpu_pressure_stress_job_002 | ok | False | False | False | native_dependency_bad_endpoint/ | native_cpu_pressure_stress_job/delete_stress_job | 190.841 |
| 45 | native_cpu_pressure_stress_job_003 | ok | False | False | False | native_dependency_bad_endpoint/wait_and_monitor | native_cpu_pressure_stress_job/delete_stress_job | 34.285 |
| 46 | native_memory_pressure_stress_job_001 | ok | False | False | False | native_dependency_bad_endpoint/restart_pod | native_memory_pressure_stress_job/delete_stress_job | 35.493 |
| 47 | native_memory_pressure_stress_job_002 | ok | True | True | True | native_memory_pressure_stress_job/delete_stress_job | native_memory_pressure_stress_job/delete_stress_job | 33.16 |
| 48 | native_memory_pressure_stress_job_003 | ok | True | True | True | native_memory_pressure_stress_job/delete_stress_job | native_memory_pressure_stress_job/delete_stress_job | 32.887 |
