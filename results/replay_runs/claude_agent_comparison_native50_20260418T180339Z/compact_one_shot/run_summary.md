# Claude compact_one_shot Native 50

- Run root: `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/replay_runs/claude_agent_comparison_native50_20260418T180339Z/compact_one_shot`
- Completed: 50/50
- Exact diagnosis correct: 27/50
- Family diagnosis correct: 32/50
- Action correct: 23/50
- Avg seconds: 8.009

| Episode | Status | Seconds | Exact | Family | Action | Submitted | Expected | Error |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| native_service_port_mismatch_productcatalogservice_001 | candidate | 8.066 | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| native_service_port_mismatch_productcatalogservice_002 | candidate | 7.175 | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| native_service_port_mismatch_productcatalogservice_003 | candidate | 9.121 | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| native_service_port_mismatch_productcatalogservice_004 | candidate | 9.395 | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| native_service_port_mismatch_productcatalogservice_005 | candidate | 6.756 | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| native_service_selector_mismatch_cartservice_001 | candidate | 7.568 | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector |  |
| native_service_selector_mismatch_cartservice_002 | candidate | 8.194 | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector |  |
| native_service_selector_mismatch_cartservice_003 | candidate | 6.179 | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector |  |
| native_service_selector_mismatch_cartservice_004 | candidate | 7.135 | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector |  |
| native_service_selector_mismatch_cartservice_005 | candidate | 6.345 | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector |  |
| native_bad_image_productcatalogservice_001 | candidate | 7.268 | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_bad_image_productcatalogservice_002 | candidate | 8.097 | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_bad_image_productcatalogservice_003 | candidate | 6.857 | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_bad_image_productcatalogservice_005 | candidate | 8.768 | True | True | True | native_bad_image/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_bad_image_productcatalogservice_006 | candidate | 8.01 | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_bad_probe_cartservice_001 | candidate | 6.042 | True | True | False | native_bad_probe/rollout_restart | native_bad_probe_rollout/rollout_undo |  |
| native_bad_probe_cartservice_002 | candidate | 7.09 | True | True | False | native_bad_probe/patch_resources | native_bad_probe_rollout/rollout_undo |  |
| native_bad_probe_cartservice_003 | candidate | 7.537 | True | True | False | native_bad_probe/patch_resources | native_bad_probe_rollout/rollout_undo |  |
| native_bad_probe_cartservice_004 | candidate | 6.854 | True | True | False | native_bad_probe/patch_resources | native_bad_probe_rollout/rollout_undo |  |
| native_bad_probe_cartservice_005 | candidate | 5.065 | True | True | False | native_bad_probe/patch_resources | native_bad_probe_rollout/rollout_undo |  |
| native_scale_zero_recommendationservice_001 | candidate | 8.048 | False | False | False | native_bad_probe/rollout_restart | native_scale_zero/scale_deployment |  |
| native_scale_zero_recommendationservice_002 | candidate | 6.518 | True | True | True | native_scale_zero/scale_deployment | native_scale_zero/scale_deployment |  |
| native_scale_zero_recommendationservice_004 | candidate | 6.238 | False | False | False | native_service_port_mismatch/patch_service_target_port | native_scale_zero/scale_deployment |  |
| native_pod_delete_cartservice_001 | candidate | 6.698 | False | False | False | native_bad_probe/patch_resources | native_pod_delete/wait_and_monitor |  |
| native_pod_delete_cartservice_002 | candidate | 8.179 | False | False | False | native_bad_probe/restart_pod | native_pod_delete/wait_and_monitor |  |
| native_pod_delete_cartservice_003 | candidate | 6.074 | False | False | False | native_memory_limit_oom/patch_resources | native_pod_delete/wait_and_monitor |  |
| native_pod_delete_cartservice_004 | candidate | 6.966 | False | False | True | native_bad_image_rollout/wait_and_monitor | native_pod_delete/wait_and_monitor |  |
| native_pod_delete_cartservice_005 | candidate | 6.809 | False | False | False | native_bad_probe/restart_pod | native_pod_delete/wait_and_monitor |  |
| native_dependency_bad_endpoint_frontend_cartservice_002 | candidate | 7.766 | False | False | False | native_bad_probe/restart_pod | native_dependency_bad_endpoint/rollout_undo |  |
| native_dependency_bad_endpoint_frontend_cartservice_003 | candidate | 9.99 | False | True | False | native_bad_env/patch_resources_then_scale | native_dependency_bad_endpoint/rollout_undo |  |
| native_dependency_bad_endpoint_frontend_cartservice_004 | candidate | 8.246 | True | True | False | native_dependency_bad_endpoint/patch_resources | native_dependency_bad_endpoint/rollout_undo |  |
| native_dependency_bad_endpoint_frontend_cartservice_005 | candidate | 9.596 | False | True | False | native_bad_env/patch_resources | native_dependency_bad_endpoint/rollout_undo |  |
| native_dependency_bad_endpoint_frontend_cartservice_006 | candidate | 7.508 | False | True | False | native_bad_env/patch_resources | native_dependency_bad_endpoint/rollout_undo |  |
| native_bad_env_checkoutservice_email_001 | candidate | 8.147 | False | False | False | native_cpu_limit_throttle/patch_resources | native_bad_env/rollout_undo |  |
| native_bad_env_checkoutservice_email_002 | candidate | 8.808 | False | False | False | native_bad_image_rollout/wait_and_monitor | native_bad_env/rollout_undo |  |
| native_bad_env_checkoutservice_email_003 | candidate | 8.123 | False | True | False | native_dependency_bad_endpoint/wait_and_monitor | native_bad_env/rollout_undo |  |
| native_bad_env_checkoutservice_email_004 | candidate | 8.125 | False | False | False | native_bad_probe/restart_pod | native_bad_env/rollout_undo |  |
| native_bad_env_checkoutservice_email_005 | candidate | 8.49 | False | True | False | native_dependency_bad_endpoint/wait_and_monitor | native_bad_env/rollout_undo |  |
| native_cpu_limit_throttle_checkoutservice_001 | candidate | 10.451 | True | True | True | native_cpu_limit_throttle/patch_resources | native_cpu_limit_throttle/patch_resources |  |
| native_cpu_limit_throttle_checkoutservice_002 | candidate | 11.612 | True | True | True | native_cpu_limit_throttle/patch_resources | native_cpu_limit_throttle/patch_resources |  |
| native_cpu_limit_throttle_checkoutservice_003 | candidate | 8.664 | True | True | True | native_cpu_limit_throttle/patch_resources | native_cpu_limit_throttle/patch_resources |  |
| native_memory_limit_oom_cartservice_001 | candidate | 8.289 | False | False | True | native_cpu_limit_throttle/patch_resources | native_memory_limit_oom/patch_resources |  |
| native_memory_limit_oom_cartservice_002 | candidate | 9.011 | True | True | True | native_memory_limit_oom/patch_resources | native_memory_limit_oom/patch_resources |  |
| native_memory_limit_oom_cartservice_003 | candidate | 10.923 | True | True | True | native_memory_limit_oom/patch_resources | native_memory_limit_oom/patch_resources |  |
| native_cpu_pressure_stress_job_001 | candidate | 9.227 | False | False | False | /wait_and_monitor | native_cpu_pressure_stress_job/delete_stress_job |  |
| native_cpu_pressure_stress_job_002 | candidate | 8.451 | False | False | False | native_bad_image/restart_pod | native_cpu_pressure_stress_job/delete_stress_job |  |
| native_cpu_pressure_stress_job_003 | candidate | 10.474 | False | False | False | native_cpu_limit_throttle/patch_resources | native_cpu_pressure_stress_job/delete_stress_job |  |
| native_memory_pressure_stress_job_001 | candidate | 10.99 | False | False | False | native_dependency_bad_endpoint/wait_and_monitor | native_memory_pressure_stress_job/delete_stress_job |  |
| native_memory_pressure_stress_job_002 | candidate | 8.884 | False | False | False | /wait_and_monitor | native_memory_pressure_stress_job/delete_stress_job |  |
| native_memory_pressure_stress_job_003 | candidate | 5.614 | False | False | False | native_cpu_limit_throttle/patch_resources | native_memory_pressure_stress_job/delete_stress_job |  |
