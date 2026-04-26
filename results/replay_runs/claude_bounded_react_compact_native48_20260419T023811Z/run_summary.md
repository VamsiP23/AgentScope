# Claude Bounded ReAct Compact Native48

- Generated: `2026-04-19T07:24:07Z`
- Run root: `<repo-root>/results/replay_runs/claude_bounded_react_compact_native48_20260419T023811Z`
- Manifest: `<repo-root>/configs/episode_sets/native_50.yaml` (`native_48_strict_good`)
- Completed/evaluated: 48/48
- Exact/family/action: 33/48 / 34/48 / 35/48
- Cooldown: 75s between episodes; 180s after 429.

| # | Episode | Status | Attempts | Seconds | Exact | Family | Action | Submitted | Expected |
|---:|---|---|---:|---:|---:|---:|---:|---|---|
| 1 | `native_service_port_mismatch_productcatalogservice_001` | ok |  | 84.254 | True | True | True | `native_service_port_mismatch/patch_service_target_port` | `native_service_port_mismatch/patch_service_target_port` |
| 2 | `native_service_port_mismatch_productcatalogservice_002` | ok |  | 102.423 | True | True | True | `native_service_port_mismatch/patch_service_target_port` | `native_service_port_mismatch/patch_service_target_port` |
| 3 | `native_service_port_mismatch_productcatalogservice_003` | ok |  | 82.599 | True | True | True | `native_service_port_mismatch/patch_service_target_port` | `native_service_port_mismatch/patch_service_target_port` |
| 4 | `native_service_port_mismatch_productcatalogservice_004` | ok |  | 116.112 | True | True | True | `native_service_port_mismatch/patch_service_target_port` | `native_service_port_mismatch/patch_service_target_port` |
| 5 | `native_service_port_mismatch_productcatalogservice_005` | ok |  | 85.677 | True | True | True | `native_service_port_mismatch/patch_service_target_port` | `native_service_port_mismatch/patch_service_target_port` |
| 6 | `native_service_selector_mismatch_cartservice_001` | ok | 1 | 110.415 | True | True | True | `native_service_selector_mismatch/patch_service_selector` | `native_service_selector_mismatch/patch_service_selector` |
| 7 | `native_service_selector_mismatch_cartservice_002` | ok | 1 | 143.365 | True | True | True | `native_service_selector_mismatch/patch_service_selector` | `native_service_selector_mismatch/patch_service_selector` |
| 8 | `native_service_selector_mismatch_cartservice_003` | ok | 1 | 72.871 | True | True | True | `native_service_selector_mismatch/patch_service_selector` | `native_service_selector_mismatch/patch_service_selector` |
| 9 | `native_service_selector_mismatch_cartservice_004` | ok | 1 | 191.983 | True | True | True | `native_service_selector_mismatch/patch_service_selector` | `native_service_selector_mismatch/patch_service_selector` |
| 10 | `native_service_selector_mismatch_cartservice_005` | ok | 1 | 168.856 | True | True | True | `native_service_selector_mismatch/patch_service_selector` | `native_service_selector_mismatch/patch_service_selector` |
| 11 | `native_bad_image_productcatalogservice_001` | ok | 1 | 146.718 | True | True | True | `native_bad_image_rollout/rollout_undo` | `native_bad_image_rollout/rollout_undo` |
| 12 | `native_bad_image_productcatalogservice_002` | ok | 1 | 145.586 | True | True | True | `native_bad_image_rollout/rollout_undo` | `native_bad_image_rollout/rollout_undo` |
| 13 | `native_bad_image_productcatalogservice_003` | ok | 1 | 230.676 | True | True | True | `native_bad_image_rollout/rollout_undo` | `native_bad_image_rollout/rollout_undo` |
| 14 | `native_bad_image_productcatalogservice_005` | ok | 1 | 83.623 | True | True | True | `native_bad_image_rollout/rollout_undo` | `native_bad_image_rollout/rollout_undo` |
| 15 | `native_bad_image_productcatalogservice_006` | ok | 1 | 289.851 | True | True | True | `native_bad_image_rollout/rollout_undo` | `native_bad_image_rollout/rollout_undo` |
| 16 | `native_bad_probe_cartservice_001` | ok | 1 | 223.085 | False | False | True | `rollout_failure/rollout_undo` | `native_bad_probe_rollout/rollout_undo` |
| 17 | `native_bad_probe_cartservice_002` | ok | 1 | 219.557 | True | True | True | `native_bad_probe_rollout/rollout_undo` | `native_bad_probe_rollout/rollout_undo` |
| 18 | `native_bad_probe_cartservice_003` | ok | 1 | 220.756 | True | True | True | `native_bad_probe_rollout/rollout_undo` | `native_bad_probe_rollout/rollout_undo` |
| 19 | `native_bad_probe_cartservice_004` | ok | 1 | 213.517 | True | True | True | `native_bad_probe_rollout/rollout_undo` | `native_bad_probe_rollout/rollout_undo` |
| 20 | `native_bad_probe_cartservice_005` | ok | 1 | 191.489 | True | True | False | `native_bad_probe_rollout/patch_resources` | `native_bad_probe_rollout/rollout_undo` |
| 21 | `native_scale_zero_recommendationservice_001` | ok | 1 | 214.765 | True | True | True | `native_scale_zero/scale_deployment` | `native_scale_zero/scale_deployment` |
| 22 | `native_scale_zero_recommendationservice_002` | ok | 1 | 196.859 | True | True | True | `native_scale_zero/scale_deployment` | `native_scale_zero/scale_deployment` |
| 23 | `native_scale_zero_recommendationservice_004` | ok | 1 | 178.565 | True | True | True | `native_scale_zero/scale_deployment` | `native_scale_zero/scale_deployment` |
| 24 | `native_pod_delete_cartservice_001` | ok | 1 | 200.051 | False | False | False | `native_bad_probe_rollout/rollout_undo` | `native_pod_delete/wait_and_monitor` |
| 25 | `native_pod_delete_cartservice_002` | ok | 1 | 252.724 | False | False | False | `native_bad_probe_rollout/rollout_restart` | `native_pod_delete/wait_and_monitor` |
| 26 | `native_pod_delete_cartservice_004` | ok | 1 | 197.593 | False | False | True | `native_dependency_bad_endpoint/wait_and_monitor` | `native_pod_delete/wait_and_monitor` |
| 27 | `native_pod_delete_cartservice_005` | ok | 1 | 187.278 | False | False | False | `pod_disturbance/rollout_restart` | `native_pod_delete/wait_and_monitor` |
| 28 | `native_dependency_bad_endpoint_frontend_cartservice_002` | ok | 2 | 226.665 | False | True | True | `native_bad_env/rollout_undo` | `native_dependency_bad_endpoint/rollout_undo` |
| 29 | `native_dependency_bad_endpoint_frontend_cartservice_003` | ok | 1 | 313.013 | False | False | False | `native_memory_limit_oom/patch_resources` | `native_dependency_bad_endpoint/rollout_undo` |
| 30 | `native_dependency_bad_endpoint_frontend_cartservice_004` | ok | 1 | 201.594 | False | False | False | `native_bad_probe_rollout/rollout_restart` | `native_dependency_bad_endpoint/rollout_undo` |
| 31 | `native_dependency_bad_endpoint_frontend_cartservice_005` | ok | 2 | 259.913 | False | False | False | `native_dependency_bad_endpoint/rollout_restart` | `native_dependency_bad_endpoint/rollout_undo` |
| 32 | `native_dependency_bad_endpoint_frontend_cartservice_006` | ok | 2 | 231.032 | False | False | False | `native_bad_probe_rollout/rollout_undo` | `native_dependency_bad_endpoint/rollout_undo` |
| 33 | `native_bad_env_checkoutservice_email_001` | ok | 1 | 184.539 | False | False | False | `native_cpu_limit_throttle/patch_resources` | `native_bad_env/rollout_undo` |
| 34 | `native_bad_env_checkoutservice_email_002` | ok | 1 | 244.896 | False | False | False | `native_bad_probe_rollout/rollout_restart` | `native_bad_env/rollout_undo` |
| 35 | `native_bad_env_checkoutservice_email_003` | ok | 1 | 160.023 | False | False | False | `pod_disturbance/rollout_restart` | `native_bad_env/rollout_undo` |
| 36 | `native_bad_env_checkoutservice_email_004` | ok | 1 | 190.946 | False | False | False | `native_bad_probe_rollout/rollout_restart` | `native_bad_env/rollout_undo` |
| 37 | `native_bad_env_checkoutservice_email_005` | ok | 1 | 286.404 | True | True | False | `native_bad_env/patch_resources` | `native_bad_env/rollout_undo` |
| 38 | `native_cpu_limit_throttle_checkoutservice_001` | ok | 1 | 203.497 | True | True | True | `native_cpu_limit_throttle/patch_resources` | `native_cpu_limit_throttle/patch_resources` |
| 39 | `native_cpu_limit_throttle_checkoutservice_002` | ok | 1 | 153.591 | True | True | True | `native_cpu_limit_throttle/patch_resources` | `native_cpu_limit_throttle/patch_resources` |
| 40 | `native_cpu_limit_throttle_checkoutservice_003` | ok | 1 | 147.928 | True | True | True | `native_cpu_limit_throttle/patch_resources` | `native_cpu_limit_throttle/patch_resources` |
| 41 | `native_memory_limit_oom_cartservice_002` | ok | 1 | 187.477 | False | False | True | `native_cpu_limit_throttle/patch_resources` | `native_memory_limit_oom/patch_resources` |
| 42 | `native_memory_limit_oom_cartservice_003` | ok | 1 | 76.473 | True | True | True | `native_memory_limit_oom/patch_resources` | `native_memory_limit_oom/patch_resources` |
| 43 | `native_cpu_pressure_stress_job_001` | ok | 1 | 159.284 | True | True | True | `native_cpu_pressure_stress_job/delete_stress_job` | `native_cpu_pressure_stress_job/delete_stress_job` |
| 44 | `native_cpu_pressure_stress_job_002` | ok | 1 | 175.459 | True | True | True | `native_cpu_pressure_stress_job/delete_stress_job` | `native_cpu_pressure_stress_job/delete_stress_job` |
| 45 | `native_cpu_pressure_stress_job_003` | ok | 1 | 156.306 | True | True | True | `native_cpu_pressure_stress_job/delete_stress_job` | `native_cpu_pressure_stress_job/delete_stress_job` |
| 46 | `native_memory_pressure_stress_job_001` | ok | 1 | 180.61 | True | True | True | `native_memory_pressure_stress_job/delete_stress_job` | `native_memory_pressure_stress_job/delete_stress_job` |
| 47 | `native_memory_pressure_stress_job_002` | ok | 1 | 155.47 | True | True | True | `native_memory_pressure_stress_job/delete_stress_job` | `native_memory_pressure_stress_job/delete_stress_job` |
| 48 | `native_memory_pressure_stress_job_003` | ok | 1 | 142.398 | True | True | True | `native_memory_pressure_stress_job/delete_stress_job` | `native_memory_pressure_stress_job/delete_stress_job` |
