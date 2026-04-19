# Gemini Compact Native 50 Refined

- Run root: `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/replay_runs/gemini_compact_native50_refined_20260418T202746Z`
- Commit: `195b678`
- Model: `gemini-2.5-flash`
- Completed: 50/50
- Exact diagnosis correct: 30/50
- Family diagnosis correct: 36/50
- Action correct: 37/50
- Avg seconds: 14.889

| Episode | Status | Seconds | Exact | Family | Action | Submitted | Expected | Error |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| native_service_port_mismatch_productcatalogservice_001 | ok | 9.099 | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| native_service_port_mismatch_productcatalogservice_002 | ok | 13.353 | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| native_service_port_mismatch_productcatalogservice_003 | ok | 11.077 | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| native_service_port_mismatch_productcatalogservice_004 | ok | 12.64 | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| native_service_port_mismatch_productcatalogservice_005 | ok | 28.219 | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| native_service_selector_mismatch_cartservice_001 | ok | 10.435 | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector |  |
| native_service_selector_mismatch_cartservice_002 | ok | 8.483 | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector |  |
| native_service_selector_mismatch_cartservice_003 | ok | 8.645 | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector |  |
| native_service_selector_mismatch_cartservice_004 | ok | 14.012 | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector |  |
| native_service_selector_mismatch_cartservice_005 | ok | 10.971 | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector |  |
| native_bad_image_productcatalogservice_001 | ok | 12.208 | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_bad_image_productcatalogservice_002 | ok | 13.018 | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_bad_image_productcatalogservice_003 | ok | 19.0 | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_bad_image_productcatalogservice_005 | ok | 13.462 | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_bad_image_productcatalogservice_006 | ok | 28.117 | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_bad_probe_cartservice_001 | ok | 9.828 | True | True | True | native_bad_probe_rollout/rollout_undo | native_bad_probe_rollout/rollout_undo |  |
| native_bad_probe_cartservice_002 | ok | 13.288 | True | True | True | native_bad_probe_rollout/rollout_undo | native_bad_probe_rollout/rollout_undo |  |
| native_bad_probe_cartservice_003 | ok | 13.503 | True | True | True | native_bad_probe_rollout/rollout_undo | native_bad_probe_rollout/rollout_undo |  |
| native_bad_probe_cartservice_004 | ok | 9.129 | True | True | True | native_bad_probe_rollout/rollout_undo | native_bad_probe_rollout/rollout_undo |  |
| native_bad_probe_cartservice_005 | ok | 18.119 | True | True | True | native_bad_probe_rollout/rollout_undo | native_bad_probe_rollout/rollout_undo |  |
| native_scale_zero_recommendationservice_001 | ok | 10.197 | True | True | True | native_scale_zero/scale_deployment | native_scale_zero/scale_deployment |  |
| native_scale_zero_recommendationservice_002 | ok | 7.197 | True | True | True | native_scale_zero/scale_deployment | native_scale_zero/scale_deployment |  |
| native_scale_zero_recommendationservice_004 | ok | 10.382 | True | True | True | native_scale_zero/scale_deployment | native_scale_zero/scale_deployment |  |
| native_pod_delete_cartservice_001 | ok | 10.235 | True | True | True | native_pod_delete/wait_and_monitor | native_pod_delete/wait_and_monitor |  |
| native_pod_delete_cartservice_002 | ok | 17.76 | False | False | False | native_bad_env/rollout_undo | native_pod_delete/wait_and_monitor |  |
| native_pod_delete_cartservice_003 | ok | 14.361 | False | False | False | native_memory_limit_oom/patch_resources | native_pod_delete/wait_and_monitor |  |
| native_pod_delete_cartservice_004 | ok | 27.366 | False | False | False | native_bad_image_rollout/rollout_undo | native_pod_delete/wait_and_monitor |  |
| native_pod_delete_cartservice_005 | ok | 11.806 | False | False | False | native_bad_probe_rollout/rollout_undo | native_pod_delete/wait_and_monitor |  |
| native_dependency_bad_endpoint_frontend_cartservice_002 | ok | 14.232 | False | True | True | native_bad_env/rollout_undo | native_dependency_bad_endpoint/rollout_undo |  |
| native_dependency_bad_endpoint_frontend_cartservice_003 | ok | 12.764 | False | True | True | native_bad_env/rollout_undo | native_dependency_bad_endpoint/rollout_undo |  |
| native_dependency_bad_endpoint_frontend_cartservice_004 | ok | 11.188 | False | True | True | native_bad_env/rollout_undo | native_dependency_bad_endpoint/rollout_undo |  |
| native_dependency_bad_endpoint_frontend_cartservice_005 | ok | 18.108 | True | True | True | native_dependency_bad_endpoint/rollout_undo | native_dependency_bad_endpoint/rollout_undo |  |
| native_dependency_bad_endpoint_frontend_cartservice_006 | ok | 15.812 | True | True | True | native_dependency_bad_endpoint/rollout_undo | native_dependency_bad_endpoint/rollout_undo |  |
| native_bad_env_checkoutservice_email_001 | ok | 13.707 | False | False | False | native_cpu_limit_throttle/patch_resources | native_bad_env/rollout_undo |  |
| native_bad_env_checkoutservice_email_002 | ok | 17.007 | False | True | False | native_dependency_bad_endpoint/rollout_restart | native_bad_env/rollout_undo |  |
| native_bad_env_checkoutservice_email_003 | ok | 15.409 | False | True | True | native_dependency_bad_endpoint/rollout_undo | native_bad_env/rollout_undo |  |
| native_bad_env_checkoutservice_email_004 | ok | 37.912 | False | False | True | native_bad_probe_rollout/rollout_undo | native_bad_env/rollout_undo |  |
| native_bad_env_checkoutservice_email_005 | ok | 20.277 | False | True | True | native_dependency_bad_endpoint/rollout_undo | native_bad_env/rollout_undo |  |
| native_cpu_limit_throttle_checkoutservice_001 | ok | 11.739 | True | True | True | native_cpu_limit_throttle/patch_resources | native_cpu_limit_throttle/patch_resources |  |
| native_cpu_limit_throttle_checkoutservice_002 | ok | 20.276 | False | False | False | native_bad_probe_rollout/rollout_undo | native_cpu_limit_throttle/patch_resources |  |
| native_cpu_limit_throttle_checkoutservice_003 | ok | 12.733 | True | True | True | native_cpu_limit_throttle/patch_resources | native_cpu_limit_throttle/patch_resources |  |
| native_memory_limit_oom_cartservice_001 | ok | 14.289 | False | False | True | native_cpu_limit_throttle/patch_resources | native_memory_limit_oom/patch_resources |  |
| native_memory_limit_oom_cartservice_002 | ok | 10.567 | True | True | True | native_memory_limit_oom/patch_resources | native_memory_limit_oom/patch_resources |  |
| native_memory_limit_oom_cartservice_003 | ok | 9.228 | True | True | True | native_memory_limit_oom/patch_resources | native_memory_limit_oom/patch_resources |  |
| native_cpu_pressure_stress_job_001 | ok | 16.127 | False | False | False | native_bad_image/rollout_undo | native_cpu_pressure_stress_job/delete_stress_job |  |
| native_cpu_pressure_stress_job_002 | ok | 14.339 | False | False | False | native_pod_delete/wait_and_monitor | native_cpu_pressure_stress_job/delete_stress_job |  |
| native_cpu_pressure_stress_job_003 | ok | 13.707 | False | False | False | native_pod_delete/wait_and_monitor | native_cpu_pressure_stress_job/delete_stress_job |  |
| native_memory_pressure_stress_job_001 | ok | 16.266 | False | False | False | native_dependency_bad_endpoint/rollout_restart | native_memory_pressure_stress_job/delete_stress_job |  |
| native_memory_pressure_stress_job_002 | ok | 18.867 | False | False | False | native_bad_image/rollout_undo | native_memory_pressure_stress_job/delete_stress_job |  |
| native_memory_pressure_stress_job_003 | ok | 23.984 | False | False | False | native_dependency_bad_endpoint/rollout_restart | native_memory_pressure_stress_job/delete_stress_job |  |
