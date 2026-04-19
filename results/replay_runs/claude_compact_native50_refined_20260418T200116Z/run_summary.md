# Claude Compact Native 50 Refined

- Run root: `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/replay_runs/claude_compact_native50_refined_20260418T200116Z`
- Commit: `195b678`
- Completed: 50/50
- Exact diagnosis correct: 33/50
- Family diagnosis correct: 37/50
- Action correct: 39/50
- Avg seconds: 8.752

| Episode | Status | Seconds | Exact | Family | Action | Submitted | Expected | Error |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| native_service_port_mismatch_productcatalogservice_001 | candidate | 7.77 | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| native_service_port_mismatch_productcatalogservice_002 | candidate | 7.323 | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| native_service_port_mismatch_productcatalogservice_003 | candidate | 6.751 | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| native_service_port_mismatch_productcatalogservice_004 | candidate | 7.776 | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| native_service_port_mismatch_productcatalogservice_005 | candidate | 6.154 | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| native_service_selector_mismatch_cartservice_001 | candidate | 7.258 | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector |  |
| native_service_selector_mismatch_cartservice_002 | candidate | 6.677 | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector |  |
| native_service_selector_mismatch_cartservice_003 | candidate | 6.224 | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector |  |
| native_service_selector_mismatch_cartservice_004 | candidate | 6.135 | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector |  |
| native_service_selector_mismatch_cartservice_005 | candidate | 6.964 | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector |  |
| native_bad_image_productcatalogservice_001 | candidate | 7.371 | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_bad_image_productcatalogservice_002 | candidate | 7.68 | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_bad_image_productcatalogservice_003 | candidate | 6.306 | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_bad_image_productcatalogservice_005 | candidate | 8.126 | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_bad_image_productcatalogservice_006 | candidate | 8.599 | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_bad_probe_cartservice_001 | candidate | 7.474 | True | True | True | native_bad_probe_rollout/rollout_undo | native_bad_probe_rollout/rollout_undo |  |
| native_bad_probe_cartservice_002 | candidate | 7.979 | True | True | True | native_bad_probe_rollout/rollout_undo | native_bad_probe_rollout/rollout_undo |  |
| native_bad_probe_cartservice_003 | candidate | 7.053 | True | True | True | native_bad_probe_rollout/rollout_undo | native_bad_probe_rollout/rollout_undo |  |
| native_bad_probe_cartservice_004 | candidate | 7.384 | True | True | True | native_bad_probe_rollout/rollout_undo | native_bad_probe_rollout/rollout_undo |  |
| native_bad_probe_cartservice_005 | candidate | 5.925 | False | False | False | native_pod_delete/wait_and_monitor | native_bad_probe_rollout/rollout_undo |  |
| native_scale_zero_recommendationservice_001 | candidate | 6.459 | True | True | True | native_scale_zero/scale_deployment | native_scale_zero/scale_deployment |  |
| native_scale_zero_recommendationservice_002 | candidate | 6.446 | True | True | True | native_scale_zero/scale_deployment | native_scale_zero/scale_deployment |  |
| native_scale_zero_recommendationservice_004 | candidate | 6.717 | True | True | True | native_scale_zero/scale_deployment | native_scale_zero/scale_deployment |  |
| native_pod_delete_cartservice_001 | candidate | 7.704 | True | True | True | native_pod_delete/wait_and_monitor | native_pod_delete/wait_and_monitor |  |
| native_pod_delete_cartservice_002 | candidate | 7.786 | True | True | True | native_pod_delete/wait_and_monitor | native_pod_delete/wait_and_monitor |  |
| native_pod_delete_cartservice_003 | candidate | 6.177 | False | False | False | native_memory_limit_oom/patch_resources | native_pod_delete/wait_and_monitor |  |
| native_pod_delete_cartservice_004 | candidate | 9.607 | False | False | False | native_scale_zero/scale_deployment | native_pod_delete/wait_and_monitor |  |
| native_pod_delete_cartservice_005 | candidate | 5.36 | True | True | True | native_pod_delete/wait_and_monitor | native_pod_delete/wait_and_monitor |  |
| native_dependency_bad_endpoint_frontend_cartservice_002 | candidate | 13.877 | False | True | True | native_bad_env/rollout_undo | native_dependency_bad_endpoint/rollout_undo |  |
| native_dependency_bad_endpoint_frontend_cartservice_003 | candidate | 54.005 | False | True | True | native_bad_env/rollout_undo | native_dependency_bad_endpoint/rollout_undo |  |
| native_dependency_bad_endpoint_frontend_cartservice_004 | candidate | 8.801 | True | True | True | native_dependency_bad_endpoint/rollout_undo | native_dependency_bad_endpoint/rollout_undo |  |
| native_dependency_bad_endpoint_frontend_cartservice_005 | candidate | 9.677 | True | True | True | native_dependency_bad_endpoint/rollout_undo | native_dependency_bad_endpoint/rollout_undo |  |
| native_dependency_bad_endpoint_frontend_cartservice_006 | candidate | 9.117 | True | True | True | native_dependency_bad_endpoint/rollout_undo | native_dependency_bad_endpoint/rollout_undo |  |
| native_bad_env_checkoutservice_email_001 | candidate | 8.064 | False | False | False | native_cpu_limit_throttle/patch_resources | native_bad_env/rollout_undo |  |
| native_bad_env_checkoutservice_email_002 | candidate | 8.596 | False | False | False | native_pod_delete/wait_and_monitor | native_bad_env/rollout_undo |  |
| native_bad_env_checkoutservice_email_003 | candidate | 4.686 | False | True | True | native_dependency_bad_endpoint/rollout_undo | native_bad_env/rollout_undo |  |
| native_bad_env_checkoutservice_email_004 | candidate | 9.885 | False | False | True | native_bad_probe_rollout/rollout_undo | native_bad_env/rollout_undo |  |
| native_bad_env_checkoutservice_email_005 | candidate | 4.032 | False | True | True | native_dependency_bad_endpoint/rollout_undo | native_bad_env/rollout_undo |  |
| native_cpu_limit_throttle_checkoutservice_001 | candidate | 11.495 | True | True | True | native_cpu_limit_throttle/patch_resources | native_cpu_limit_throttle/patch_resources |  |
| native_cpu_limit_throttle_checkoutservice_002 | candidate | 7.664 | True | True | True | native_cpu_limit_throttle/patch_resources | native_cpu_limit_throttle/patch_resources |  |
| native_cpu_limit_throttle_checkoutservice_003 | candidate | 11.469 | True | True | True | native_cpu_limit_throttle/patch_resources | native_cpu_limit_throttle/patch_resources |  |
| native_memory_limit_oom_cartservice_001 | candidate | 11.142 | False | False | True | native_cpu_limit_throttle/patch_resources | native_memory_limit_oom/patch_resources |  |
| native_memory_limit_oom_cartservice_002 | candidate | 11.503 | True | True | True | native_memory_limit_oom/patch_resources | native_memory_limit_oom/patch_resources |  |
| native_memory_limit_oom_cartservice_003 | candidate | 4.224 | True | True | True | native_memory_limit_oom/patch_resources | native_memory_limit_oom/patch_resources |  |
| native_cpu_pressure_stress_job_001 | candidate | 6.683 | False | False | False | /wait_and_monitor | native_cpu_pressure_stress_job/delete_stress_job |  |
| native_cpu_pressure_stress_job_002 | candidate | 10.547 | False | False | False | native_bad_env/wait_and_monitor | native_cpu_pressure_stress_job/delete_stress_job |  |
| native_cpu_pressure_stress_job_003 | candidate | 3.947 | False | False | False | native_pod_delete/wait_and_monitor | native_cpu_pressure_stress_job/delete_stress_job |  |
| native_memory_pressure_stress_job_001 | candidate | 8.056 | False | False | False | native_dependency_bad_endpoint/wait_and_monitor | native_memory_pressure_stress_job/delete_stress_job |  |
| native_memory_pressure_stress_job_002 | candidate | 10.5 | False | False | False | native_bad_env/wait_and_monitor | native_memory_pressure_stress_job/delete_stress_job |  |
| native_memory_pressure_stress_job_003 | candidate | 10.45 | False | False | False | native_dependency_bad_endpoint/wait_and_monitor | native_memory_pressure_stress_job/delete_stress_job |  |
