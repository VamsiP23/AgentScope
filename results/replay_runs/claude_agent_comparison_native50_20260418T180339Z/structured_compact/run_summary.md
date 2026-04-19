# Claude structured_compact Native 50

- Run root: `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/replay_runs/claude_agent_comparison_native50_20260418T180339Z/structured_compact`
- Completed: 45/50
- Exact diagnosis correct: 24/45
- Family diagnosis correct: 27/45
- Action correct: 29/45
- Avg seconds: 74.923

| Episode | Status | Seconds | Exact | Family | Action | Submitted | Expected | Error |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| native_service_port_mismatch_productcatalogservice_001 | candidate | 38.616 | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| native_service_port_mismatch_productcatalogservice_002 | candidate | 33.787 | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| native_service_port_mismatch_productcatalogservice_003 | candidate | 24.136 | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| native_service_port_mismatch_productcatalogservice_004 | candidate | 32.063 | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| native_service_port_mismatch_productcatalogservice_005 | candidate | 29.015 | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| native_service_selector_mismatch_cartservice_001 | candidate | 30.806 | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector |  |
| native_service_selector_mismatch_cartservice_002 | candidate | 28.958 | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector |  |
| native_service_selector_mismatch_cartservice_003 | candidate | 25.187 | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector |  |
| native_service_selector_mismatch_cartservice_004 | candidate | 26.103 | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector |  |
| native_service_selector_mismatch_cartservice_005 | candidate | 27.485 | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector |  |
| native_bad_image_productcatalogservice_001 | candidate | 36.181 | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_bad_image_productcatalogservice_002 | candidate | 38.321 | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_bad_image_productcatalogservice_003 | candidate | 33.984 | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_bad_image_productcatalogservice_005 | candidate | 42.698 | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_bad_image_productcatalogservice_006 | candidate | 38.158 | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_bad_probe_cartservice_001 | candidate | 31.419 | True | True | True | native_bad_probe_rollout/rollout_undo | native_bad_probe_rollout/rollout_undo |  |
| native_bad_probe_cartservice_002 | error | 951.913 | None | None | None | None/None | None/ | Remote end closed connection without response |
| native_bad_probe_cartservice_003 | candidate | 78.579 | True | True | True | native_bad_probe_rollout/rollout_undo | native_bad_probe_rollout/rollout_undo |  |
| native_bad_probe_cartservice_004 | candidate | 353.435 | True | True | True | native_bad_probe_rollout/rollout_undo | native_bad_probe_rollout/rollout_undo |  |
| native_bad_probe_cartservice_005 | candidate | 31.3 | True | True | True | native_bad_probe_rollout/rollout_undo | native_bad_probe_rollout/rollout_undo |  |
| native_scale_zero_recommendationservice_001 | candidate | 41.311 | False | False | False | native_bad_probe_rollout/rollout_undo | native_scale_zero/scale_deployment |  |
| native_scale_zero_recommendationservice_002 | candidate | 36.04 | False | False | False | /restart_pod | native_scale_zero/scale_deployment |  |
| native_scale_zero_recommendationservice_004 | candidate | 111.591 | True | True | True | native_scale_zero/scale_deployment | native_scale_zero/scale_deployment |  |
| native_pod_delete_cartservice_001 | candidate | 33.499 | False | False | False | native_bad_probe_rollout/rollout_undo | native_pod_delete/wait_and_monitor |  |
| native_pod_delete_cartservice_002 | candidate | 33.307 | False | False | False | native_bad_probe_rollout/rollout_undo | native_pod_delete/wait_and_monitor |  |
| native_pod_delete_cartservice_003 | candidate | 212.687 | False | False | False | native_memory_limit_oom/patch_resources | native_pod_delete/wait_and_monitor |  |
| native_pod_delete_cartservice_004 | candidate | 30.827 | False | False | False | native_bad_probe_rollout/rollout_undo | native_pod_delete/wait_and_monitor |  |
| native_pod_delete_cartservice_005 | candidate | 29.839 | False | False | False | native_bad_probe_rollout/rollout_undo | native_pod_delete/wait_and_monitor |  |
| native_dependency_bad_endpoint_frontend_cartservice_002 | candidate | 40.2 | True | True | True | native_dependency_bad_endpoint/rollout_undo | native_dependency_bad_endpoint/rollout_undo |  |
| native_dependency_bad_endpoint_frontend_cartservice_003 | candidate | 43.702 | False | True | True | native_bad_env/rollout_undo | native_dependency_bad_endpoint/rollout_undo |  |
| native_dependency_bad_endpoint_frontend_cartservice_004 | candidate | 38.745 | False | False | False | native_memory_limit_oom/patch_resources | native_dependency_bad_endpoint/rollout_undo |  |
| native_dependency_bad_endpoint_frontend_cartservice_005 | candidate | 34.317 | False | True | True | native_bad_env/rollout_undo | native_dependency_bad_endpoint/rollout_undo |  |
| native_dependency_bad_endpoint_frontend_cartservice_006 | error | 34.556 | None | None | None | None/None | None/ | Remote end closed connection without response |
| native_bad_env_checkoutservice_email_001 | candidate | 38.337 | False | False | False | native_cpu_limit_throttle/patch_resources | native_bad_env/rollout_undo |  |
| native_bad_env_checkoutservice_email_002 | candidate | 38.372 | False | False | True | native_bad_probe_rollout/rollout_undo | native_bad_env/rollout_undo |  |
| native_bad_env_checkoutservice_email_003 | candidate | 42.8 | False | False | False | native_dependency_bad_endpoint/scale_deployment | native_bad_env/rollout_undo |  |
| native_bad_env_checkoutservice_email_004 | candidate | 43.865 | False | False | True | native_bad_probe_rollout/rollout_undo | native_bad_env/rollout_undo |  |
| native_bad_env_checkoutservice_email_005 | candidate | 39.687 | False | True | True | native_dependency_bad_endpoint/rollout_undo | native_bad_env/rollout_undo |  |
| native_cpu_limit_throttle_checkoutservice_001 | candidate | 30.717 | True | True | True | native_cpu_limit_throttle/patch_resources | native_cpu_limit_throttle/patch_resources |  |
| native_cpu_limit_throttle_checkoutservice_002 | error | 74.335 | None | None | None | None/None | None/ | Remote end closed connection without response |
| native_cpu_limit_throttle_checkoutservice_003 | candidate | 36.508 | True | True | True | native_cpu_limit_throttle/patch_resources | native_cpu_limit_throttle/patch_resources |  |
| native_memory_limit_oom_cartservice_001 | candidate | 37.08 | False | False | False | native_bad_probe_rollout/rollout_undo | native_memory_limit_oom/patch_resources |  |
| native_memory_limit_oom_cartservice_002 | candidate | 41.137 | True | True | True | native_memory_limit_oom/patch_resources | native_memory_limit_oom/patch_resources |  |
| native_memory_limit_oom_cartservice_003 | error | 358.645 | None | None | None | None/None | None/ | Remote end closed connection without response |
| native_cpu_pressure_stress_job_001 | candidate | 36.836 | False | False | False | native_dependency_bad_endpoint/wait_and_monitor | native_cpu_pressure_stress_job/delete_stress_job |  |
| native_cpu_pressure_stress_job_002 | candidate | 38.967 | False | False | False | native_cpu_limit_throttle/patch_resources | native_cpu_pressure_stress_job/delete_stress_job |  |
| native_cpu_pressure_stress_job_003 | candidate | 39.614 | False | False | False | native_dependency_bad_endpoint/restart_pod | native_cpu_pressure_stress_job/delete_stress_job |  |
| native_memory_pressure_stress_job_001 | error | 122.977 | None | None | None | None/None | None/ | Remote end closed connection without response |
| native_memory_pressure_stress_job_002 | candidate | 46.462 | False | False | False | native_bad_image/rollout_undo | native_memory_pressure_stress_job/delete_stress_job |  |
| native_memory_pressure_stress_job_003 | candidate | 27.036 | False | False | False | native_cpu_limit_throttle/patch_resources | native_memory_pressure_stress_job/delete_stress_job |  |
