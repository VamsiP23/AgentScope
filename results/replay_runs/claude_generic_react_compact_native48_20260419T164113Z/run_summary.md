# Claude Generic ReAct Native48

- Status: `complete`
- Run root: `<repo-root>/results/replay_runs/claude_generic_react_compact_native48_20260419T164113Z`
- Completed evaluations: 48/48
- Exact: 27/48
- Grouped family: 27/48
- Action: 26/48

| # | Episode | Status | Exact | Family | Action | Submitted | Expected | Seconds |
|---:|---|---|---:|---:|---:|---|---|---:|
| 1 | native_service_port_mismatch_productcatalogservice_001 | ok | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port | 74.303 |
| 2 | native_service_port_mismatch_productcatalogservice_002 | ok | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port | 111.091 |
| 3 | native_service_port_mismatch_productcatalogservice_003 | ok | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port | 86.87 |
| 4 | native_service_port_mismatch_productcatalogservice_004 | ok | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port | 80.948 |
| 5 | native_service_port_mismatch_productcatalogservice_005 | ok | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port | 80.965 |
| 6 | native_service_selector_mismatch_cartservice_001 | ok | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector | 109.787 |
| 7 | native_service_selector_mismatch_cartservice_002 | ok | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector | 79.277 |
| 8 | native_service_selector_mismatch_cartservice_003 | ok | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector | 80.374 |
| 9 | native_service_selector_mismatch_cartservice_004 | ok | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector | 106.116 |
| 10 | native_service_selector_mismatch_cartservice_005 | ok | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector | 109.831 |
| 11 | native_bad_image_productcatalogservice_001 | ok | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo | 89.617 |
| 12 | native_bad_image_productcatalogservice_002 | ok | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo | 82.306 |
| 13 | native_bad_image_productcatalogservice_003 | ok | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo | 78.208 |
| 14 | native_bad_image_productcatalogservice_005 | ok | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo | 85.487 |
| 15 | native_bad_image_productcatalogservice_006 | ok | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo | 85.885 |
| 16 | native_bad_probe_cartservice_001 | ok | False | False | False | native_dependency_bad_endpoint/rollout_restart | native_bad_probe_rollout/rollout_undo | 186.339 |
| 17 | native_bad_probe_cartservice_002 | ok | True | True | True | native_bad_probe_rollout/rollout_undo | native_bad_probe_rollout/rollout_undo | 146.75 |
| 18 | native_bad_probe_cartservice_003 | ok | True | True | True | native_bad_probe_rollout/rollout_undo | native_bad_probe_rollout/rollout_undo | 86.53 |
| 19 | native_bad_probe_cartservice_004 | ok | True | True | False | native_bad_probe_rollout/patch_resources | native_bad_probe_rollout/rollout_undo | 117.044 |
| 20 | native_bad_probe_cartservice_005 | ok | True | True | False | native_bad_probe_rollout/patch_resources | native_bad_probe_rollout/rollout_undo | 116.725 |
| 21 | native_scale_zero_recommendationservice_001 | ok | True | True | True | native_scale_zero/scale_deployment | native_scale_zero/scale_deployment | 83.536 |
| 22 | native_scale_zero_recommendationservice_002 | ok | True | True | True | native_scale_zero/scale_deployment | native_scale_zero/scale_deployment | 116.993 |
| 23 | native_scale_zero_recommendationservice_004 | ok | True | True | True | native_scale_zero/scale_deployment | native_scale_zero/scale_deployment | 103.573 |
| 24 | native_pod_delete_cartservice_001 | ok | False | False | False | native_bad_probe_rollout/rollout_undo | native_pod_delete/wait_and_monitor | 187.672 |
| 25 | native_pod_delete_cartservice_002 | ok | False | False | False | native_bad_probe_rollout/restart_pod | native_pod_delete/wait_and_monitor | 148.454 |
| 26 | native_pod_delete_cartservice_004 | ok | False | False | False | rollout_failure/rollout_undo | native_pod_delete/wait_and_monitor | 149.553 |
| 27 | native_pod_delete_cartservice_005 | ok | False | False | False | dependency_localization/rollout_restart | native_pod_delete/wait_and_monitor | 158.735 |
| 28 | native_dependency_bad_endpoint_frontend_cartservice_002 | ok | False | False | False | runtime_failure/wait_and_monitor | native_dependency_bad_endpoint/rollout_undo | 223.729 |
| 29 | native_dependency_bad_endpoint_frontend_cartservice_003 | ok | False | False | False | partial_degradation/rollout_restart | native_dependency_bad_endpoint/rollout_undo | 191.422 |
| 30 | native_dependency_bad_endpoint_frontend_cartservice_004 | ok | False | False | False | runtime_failure/rollout_restart | native_dependency_bad_endpoint/rollout_undo | 237.944 |
| 31 | native_dependency_bad_endpoint_frontend_cartservice_005 | ok | False | False | False | native_bad_probe_rollout/rollout_restart | native_dependency_bad_endpoint/rollout_undo | 241.365 |
| 32 | native_dependency_bad_endpoint_frontend_cartservice_006 | ok | False | False | False | native_bad_probe_rollout/rollout_undo | native_dependency_bad_endpoint/rollout_undo | 131.353 |
| 33 | native_bad_env_checkoutservice_email_001 | ok | False | False | False | native_cpu_limit_throttle/patch_resources | native_bad_env/rollout_undo | 124.59 |
| 34 | native_bad_env_checkoutservice_email_002 | ok | False | False | False | pod_disturbance/rollout_restart | native_bad_env/rollout_undo | 236.422 |
| 35 | native_bad_env_checkoutservice_email_003 | ok | False | False | False | native_service_port_mismatch/patch_service_target_port | native_bad_env/rollout_undo | 194.838 |
| 36 | native_bad_env_checkoutservice_email_004 | ok | False | False | True | native_bad_probe_rollout/rollout_undo | native_bad_env/rollout_undo | 169.288 |
| 37 | native_bad_env_checkoutservice_email_005 | ok | False | False | False | native_service_port_mismatch/patch_service_target_port | native_bad_env/rollout_undo | 125.054 |
| 38 | native_cpu_limit_throttle_checkoutservice_001 | ok | True | True | True | native_cpu_limit_throttle/patch_resources | native_cpu_limit_throttle/patch_resources | 114.277 |
| 39 | native_cpu_limit_throttle_checkoutservice_002 | ok | True | True | True | native_cpu_limit_throttle/patch_resources | native_cpu_limit_throttle/patch_resources | 117.091 |
| 40 | native_cpu_limit_throttle_checkoutservice_003 | ok | True | True | True | native_cpu_limit_throttle/patch_resources | native_cpu_limit_throttle/patch_resources | 119.302 |
| 41 | native_memory_limit_oom_cartservice_002 | ok | True | True | True | native_memory_limit_oom/patch_resources | native_memory_limit_oom/patch_resources | 112.347 |
| 42 | native_memory_limit_oom_cartservice_003 | ok | True | True | True | native_memory_limit_oom/patch_resources | native_memory_limit_oom/patch_resources | 118.774 |
| 43 | native_cpu_pressure_stress_job_001 | ok | False | False | False | runtime_failure/wait_and_monitor | native_cpu_pressure_stress_job/delete_stress_job | 250.047 |
| 44 | native_cpu_pressure_stress_job_002 | ok | False | False | False | runtime_failure/wait_and_monitor | native_cpu_pressure_stress_job/delete_stress_job | 230.994 |
| 45 | native_cpu_pressure_stress_job_003 | ok | False | False | False | pod_disturbance/rollout_restart | native_cpu_pressure_stress_job/delete_stress_job | 230.015 |
| 46 | native_memory_pressure_stress_job_001 | ok | False | False | False | dependency_localization/wait_and_monitor | native_memory_pressure_stress_job/delete_stress_job | 283.322 |
| 47 | native_memory_pressure_stress_job_002 | ok | False | False | False | runtime_failure/wait_and_monitor | native_memory_pressure_stress_job/delete_stress_job | 242.597 |
| 48 | native_memory_pressure_stress_job_003 | ok | False | False | False | native_cpu_limit_throttle/patch_resources | native_memory_pressure_stress_job/delete_stress_job | 191.235 |
