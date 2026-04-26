# Ollama Llama 3.2 3B Compact Native48

- Status: `complete`
- Run root: `<repo-root>/results/replay_runs/ollama_llama32_3b_compact_native48_20260419T191820Z`
- Completed evaluations: 46/48
- Exact: 6/46
- Grouped family: 6/46
- Action: 4/46

| # | Episode | Status | Exact | Family | Action | Submitted | Expected | Seconds |
|---:|---|---|---:|---:|---:|---|---|---:|
| 1 | native_service_port_mismatch_productcatalogservice_001 | ok | False | False | False | /restart_pod | native_service_port_mismatch/patch_service_target_port | 88.991 |
| 2 | native_service_port_mismatch_productcatalogservice_002 | ok | False | False | False | / | native_service_port_mismatch/patch_service_target_port | 58.481 |
| 3 | native_service_port_mismatch_productcatalogservice_003 | ok | True | True | False | native_service_port_mismatch/scale_deployment | native_service_port_mismatch/patch_service_target_port | 28.332 |
| 4 | native_service_port_mismatch_productcatalogservice_004 | ok | False | False | False | / | native_service_port_mismatch/patch_service_target_port | 44.683 |
| 5 | native_service_port_mismatch_productcatalogservice_005 | ok | False | False | False | native_service_selector_mismatch/patch_service_selector | native_service_port_mismatch/patch_service_target_port | 39.18 |
| 6 | native_service_selector_mismatch_cartservice_001 | ok | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector | 48.204 |
| 7 | native_service_selector_mismatch_cartservice_002 | ok | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector | 39.692 |
| 8 | native_service_selector_mismatch_cartservice_003 | ok | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector | 23.896 |
| 9 | native_service_selector_mismatch_cartservice_004 | error |  |  |  |  |  | 181.74 |
| 10 | native_service_selector_mismatch_cartservice_005 | ok | True | True | False | native_service_selector_mismatch/scale_deployment | native_service_selector_mismatch/patch_service_selector | 46.091 |
| 11 | native_bad_image_productcatalogservice_001 | ok | False | False | False | native_service_port_mismatch/patch_resources | native_bad_image_rollout/rollout_undo | 45.14 |
| 12 | native_bad_image_productcatalogservice_002 | ok | False | False | False | native_service_selector_mismatch/patch_service_selector | native_bad_image_rollout/rollout_undo | 49.777 |
| 13 | native_bad_image_productcatalogservice_003 | ok | False | False | False | native_service_selector_mismatch/patch_service_selector | native_bad_image_rollout/rollout_undo | 54.253 |
| 14 | native_bad_image_productcatalogservice_005 | ok | False | False | False | / | native_bad_image_rollout/rollout_undo | 45.685 |
| 15 | native_bad_image_productcatalogservice_006 | ok | False | False | False | / | native_bad_image_rollout/rollout_undo | 50.553 |
| 16 | native_bad_probe_cartservice_001 | ok | False | False | False | native_service_selector_mismatch/patch_service_selector | native_bad_probe_rollout/rollout_undo | 29.654 |
| 17 | native_bad_probe_cartservice_002 | ok | False | False | False | native_service_selector_mismatch/scale_deployment | native_bad_probe_rollout/rollout_undo | 24.74 |
| 18 | native_bad_probe_cartservice_003 | ok | True | True | True | native_bad_probe_rollout/rollout_undo | native_bad_probe_rollout/rollout_undo | 29.89 |
| 19 | native_bad_probe_cartservice_004 | error |  |  |  |  |  | 181.809 |
| 20 | native_bad_probe_cartservice_005 | ok | False | False | False | native_service_selector_mismatch/scale_deployment | native_bad_probe_rollout/rollout_undo | 32.468 |
| 21 | native_scale_zero_recommendationservice_001 | ok | False | False | False | /restart_pod | native_scale_zero/scale_deployment | 38.375 |
| 22 | native_scale_zero_recommendationservice_002 | ok | False | False | False | native_service_selector_mismatch/patch_service_selector | native_scale_zero/scale_deployment | 31.934 |
| 23 | native_scale_zero_recommendationservice_004 | ok | False | False | False | / | native_scale_zero/scale_deployment | 42.192 |
| 24 | native_pod_delete_cartservice_001 | ok | False | False | False | native_service_selector_mismatch/patch_service_selector | native_pod_delete/wait_and_monitor | 41.337 |
| 25 | native_pod_delete_cartservice_002 | ok | False | False | False | native_service_port_mismatch/patch_service_target_port | native_pod_delete/wait_and_monitor | 34.059 |
| 26 | native_pod_delete_cartservice_004 | ok | False | False | False | native_scale_zero/scale_deployment | native_pod_delete/wait_and_monitor | 24.171 |
| 27 | native_pod_delete_cartservice_005 | ok | False | False | False | native_service_port_mismatch/patch_service_target_port | native_pod_delete/wait_and_monitor | 37.218 |
| 28 | native_dependency_bad_endpoint_frontend_cartservice_002 | ok | False | False | False | / | native_dependency_bad_endpoint/rollout_undo | 57.836 |
| 29 | native_dependency_bad_endpoint_frontend_cartservice_003 | ok | False | False | False | / | native_dependency_bad_endpoint/rollout_undo | 48.722 |
| 30 | native_dependency_bad_endpoint_frontend_cartservice_004 | ok | False | False | False | / | native_dependency_bad_endpoint/rollout_undo | 41.969 |
| 31 | native_dependency_bad_endpoint_frontend_cartservice_005 | ok | False | False | False | /restart_pod | native_dependency_bad_endpoint/rollout_undo | 50.155 |
| 32 | native_dependency_bad_endpoint_frontend_cartservice_006 | ok | False | False | False | /restart_pod | native_dependency_bad_endpoint/rollout_undo | 43.609 |
| 33 | native_bad_env_checkoutservice_email_001 | ok | False | False | False | / | native_bad_env/rollout_undo | 37.808 |
| 34 | native_bad_env_checkoutservice_email_002 | ok | False | False | False | / | native_bad_env/rollout_undo | 37.892 |
| 35 | native_bad_env_checkoutservice_email_003 | ok | False | False | False | /restart_pod | native_bad_env/rollout_undo | 41.348 |
| 36 | native_bad_env_checkoutservice_email_004 | ok | False | False | False | / | native_bad_env/rollout_undo | 41.653 |
| 37 | native_bad_env_checkoutservice_email_005 | ok | False | False | False | /restart_pod | native_bad_env/rollout_undo | 36.33 |
| 38 | native_cpu_limit_throttle_checkoutservice_001 | ok | False | False | False | native_scale_zero/patch_resources_then_scale | native_cpu_limit_throttle/patch_resources | 36.334 |
| 39 | native_cpu_limit_throttle_checkoutservice_002 | ok | False | False | False | native_scale_zero/scale_deployment | native_cpu_limit_throttle/patch_resources | 28.945 |
| 40 | native_cpu_limit_throttle_checkoutservice_003 | ok | False | False | False | / | native_cpu_limit_throttle/patch_resources | 52.372 |
| 41 | native_memory_limit_oom_cartservice_002 | ok | False | False | False | /restart_pod | native_memory_limit_oom/patch_resources | 47.059 |
| 42 | native_memory_limit_oom_cartservice_003 | ok | False | False | False | / | native_memory_limit_oom/patch_resources | 36.631 |
| 43 | native_cpu_pressure_stress_job_001 | ok | False | False | False | native_service_port_mismatch/patch_service_target_port | native_cpu_pressure_stress_job/delete_stress_job | 32.925 |
| 44 | native_cpu_pressure_stress_job_002 | ok | False | False | False | / | native_cpu_pressure_stress_job/delete_stress_job | 67.615 |
| 45 | native_cpu_pressure_stress_job_003 | ok | False | False | False | /restart_pod | native_cpu_pressure_stress_job/delete_stress_job | 48.05 |
| 46 | native_memory_pressure_stress_job_001 | ok | False | False | False | native_service_selector_mismatch/patch_resources | native_memory_pressure_stress_job/delete_stress_job | 34.309 |
| 47 | native_memory_pressure_stress_job_002 | ok | False | False | False | / | native_memory_pressure_stress_job/delete_stress_job | 31.176 |
| 48 | native_memory_pressure_stress_job_003 | ok | False | False | False | / | native_memory_pressure_stress_job/delete_stress_job | 99.827 |
