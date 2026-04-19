# OpenAI Compact Native 50 Refined

- Run root: `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/replay_runs/openai_compact_native50_refined_20260418T201827Z`
- Commit: `195b678`
- Model: `gpt-4o-mini`
- Completed: 50/50
- Exact diagnosis correct: 32/50
- Family diagnosis correct: 34/50
- Action correct: 28/50
- Avg seconds: 4.163

| Episode | Status | Seconds | Exact | Family | Action | Submitted | Expected | Error |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| native_service_port_mismatch_productcatalogservice_001 | candidate | 5.816 | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| native_service_port_mismatch_productcatalogservice_002 | candidate | 3.311 | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| native_service_port_mismatch_productcatalogservice_003 | candidate | 4.184 | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| native_service_port_mismatch_productcatalogservice_004 | candidate | 4.23 | True | True | False | native_service_port_mismatch/rollout_undo | native_service_port_mismatch/patch_service_target_port |  |
| native_service_port_mismatch_productcatalogservice_005 | candidate | 3.269 | True | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| native_service_selector_mismatch_cartservice_001 | candidate | 4.502 | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector |  |
| native_service_selector_mismatch_cartservice_002 | candidate | 3.878 | True | True | False | native_service_selector_mismatch/rollout_undo | native_service_selector_mismatch/patch_service_selector |  |
| native_service_selector_mismatch_cartservice_003 | candidate | 3.705 | True | True | False | native_service_selector_mismatch/scale_deployment | native_service_selector_mismatch/patch_service_selector |  |
| native_service_selector_mismatch_cartservice_004 | candidate | 4.102 | True | True | True | native_service_selector_mismatch/patch_service_selector | native_service_selector_mismatch/patch_service_selector |  |
| native_service_selector_mismatch_cartservice_005 | candidate | 5.257 | True | True | False | native_service_selector_mismatch/rollout_undo | native_service_selector_mismatch/patch_service_selector |  |
| native_bad_image_productcatalogservice_001 | candidate | 5.477 | True | True | True | native_bad_image/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_bad_image_productcatalogservice_002 | candidate | 3.759 | True | True | True | native_bad_image/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_bad_image_productcatalogservice_003 | candidate | 3.792 | True | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_bad_image_productcatalogservice_005 | candidate | 2.681 | True | True | True | native_bad_image/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_bad_image_productcatalogservice_006 | candidate | 4.879 | True | True | True | native_bad_image/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_bad_probe_cartservice_001 | candidate | 5.652 | True | True | False | native_bad_probe/wait_and_monitor | native_bad_probe_rollout/rollout_undo |  |
| native_bad_probe_cartservice_002 | candidate | 3.238 | False | False | False | native_pod_delete/wait_and_monitor | native_bad_probe_rollout/rollout_undo |  |
| native_bad_probe_cartservice_003 | candidate | 2.673 | False | False | False | native_pod_delete/wait_and_monitor | native_bad_probe_rollout/rollout_undo |  |
| native_bad_probe_cartservice_004 | candidate | 2.2 | False | False | False | native_pod_delete/wait_and_monitor | native_bad_probe_rollout/rollout_undo |  |
| native_bad_probe_cartservice_005 | candidate | 3.04 | True | True | False | native_bad_probe/wait_and_monitor | native_bad_probe_rollout/rollout_undo |  |
| native_scale_zero_recommendationservice_001 | candidate | 3.111 | True | True | True | native_scale_zero/scale_deployment | native_scale_zero/scale_deployment |  |
| native_scale_zero_recommendationservice_002 | candidate | 2.765 | True | True | True | native_scale_zero/scale_deployment | native_scale_zero/scale_deployment |  |
| native_scale_zero_recommendationservice_004 | candidate | 2.932 | True | True | True | native_scale_zero/scale_deployment | native_scale_zero/scale_deployment |  |
| native_pod_delete_cartservice_001 | candidate | 4.959 | True | True | True | native_pod_delete/wait_and_monitor | native_pod_delete/wait_and_monitor |  |
| native_pod_delete_cartservice_002 | candidate | 3.541 | False | False | False | native_scale_zero/scale_deployment | native_pod_delete/wait_and_monitor |  |
| native_pod_delete_cartservice_003 | candidate | 3.414 | True | True | True | native_pod_delete/wait_and_monitor | native_pod_delete/wait_and_monitor |  |
| native_pod_delete_cartservice_004 | candidate | 3.166 | True | True | True | native_pod_delete/wait_and_monitor | native_pod_delete/wait_and_monitor |  |
| native_pod_delete_cartservice_005 | candidate | 2.705 | False | False | True | native_bad_probe/wait_and_monitor | native_pod_delete/wait_and_monitor |  |
| native_dependency_bad_endpoint_frontend_cartservice_002 | candidate | 3.945 | True | True | True | native_dependency_bad_endpoint/rollout_undo | native_dependency_bad_endpoint/rollout_undo |  |
| native_dependency_bad_endpoint_frontend_cartservice_003 | candidate | 7.512 | True | True | False | native_dependency_bad_endpoint/delete_stress_job | native_dependency_bad_endpoint/rollout_undo |  |
| native_dependency_bad_endpoint_frontend_cartservice_004 | candidate | 5.259 | True | True | True | native_dependency_bad_endpoint/rollout_undo | native_dependency_bad_endpoint/rollout_undo |  |
| native_dependency_bad_endpoint_frontend_cartservice_005 | candidate | 7.177 | True | True | True | native_dependency_bad_endpoint/rollout_undo | native_dependency_bad_endpoint/rollout_undo |  |
| native_dependency_bad_endpoint_frontend_cartservice_006 | candidate | 7.538 | True | True | True | native_dependency_bad_endpoint/rollout_undo | native_dependency_bad_endpoint/rollout_undo |  |
| native_bad_env_checkoutservice_email_001 | candidate | 2.965 | False | False | False | native_memory_limit_oom/delete_stress_job | native_bad_env/rollout_undo |  |
| native_bad_env_checkoutservice_email_002 | candidate | 4.173 | False | False | False | native_memory_limit_oom/delete_stress_job | native_bad_env/rollout_undo |  |
| native_bad_env_checkoutservice_email_003 | candidate | 5.465 | False | True | True | native_dependency_bad_endpoint/rollout_undo | native_bad_env/rollout_undo |  |
| native_bad_env_checkoutservice_email_004 | candidate | 5.469 | False | False | False | native_bad_probe/wait_and_monitor | native_bad_env/rollout_undo |  |
| native_bad_env_checkoutservice_email_005 | candidate | 2.702 | False | True | True | native_dependency_bad_endpoint/rollout_undo | native_bad_env/rollout_undo |  |
| native_cpu_limit_throttle_checkoutservice_001 | candidate | 2.71 | False | False | False | native_cpu_pressure_stress_job/delete_stress_job | native_cpu_limit_throttle/patch_resources |  |
| native_cpu_limit_throttle_checkoutservice_002 | candidate | 5.74 | False | False | False | native_bad_probe/wait_and_monitor | native_cpu_limit_throttle/patch_resources |  |
| native_cpu_limit_throttle_checkoutservice_003 | candidate | 3.034 | True | True | False | native_cpu_limit_throttle/scale_deployment | native_cpu_limit_throttle/patch_resources |  |
| native_memory_limit_oom_cartservice_001 | candidate | 3.627 | False | False | False | native_cpu_limit_throttle/scale_deployment | native_memory_limit_oom/patch_resources |  |
| native_memory_limit_oom_cartservice_002 | candidate | 2.702 | True | True | False | native_memory_limit_oom/wait_and_monitor | native_memory_limit_oom/patch_resources |  |
| native_memory_limit_oom_cartservice_003 | candidate | 4.953 | True | True | False | native_memory_limit_oom/delete_stress_job | native_memory_limit_oom/patch_resources |  |
| native_cpu_pressure_stress_job_001 | candidate | 3.108 | False | False | True | native_dependency_bad_endpoint/delete_stress_job | native_cpu_pressure_stress_job/delete_stress_job |  |
| native_cpu_pressure_stress_job_002 | candidate | 3.89 | True | True | True | native_cpu_pressure_stress_job/delete_stress_job | native_cpu_pressure_stress_job/delete_stress_job |  |
| native_cpu_pressure_stress_job_003 | candidate | 7.158 | False | False | True | native_dependency_bad_endpoint/delete_stress_job | native_cpu_pressure_stress_job/delete_stress_job |  |
| native_memory_pressure_stress_job_001 | candidate | 3.92 | False | False | True | native_dependency_bad_endpoint/delete_stress_job | native_memory_pressure_stress_job/delete_stress_job |  |
| native_memory_pressure_stress_job_002 | candidate | 5.77 | False | False | False | native_dependency_bad_endpoint/wait_and_monitor | native_memory_pressure_stress_job/delete_stress_job |  |
| native_memory_pressure_stress_job_003 | candidate | 3.106 | False | False | False | native_dependency_bad_endpoint/wait_and_monitor | native_memory_pressure_stress_job/delete_stress_job |  |
