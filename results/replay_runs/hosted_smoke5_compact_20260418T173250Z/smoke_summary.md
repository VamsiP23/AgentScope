# Hosted Smoke 5 Compact One-Shot

- Run root: `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/replay_runs/hosted_smoke5_compact_20260418T173250Z`
- Manifest: `configs/episode_sets/smoke_5.yaml`
- Models: Claude Sonnet 4, OpenAI gpt-4o-mini, Gemini 2.5 Flash
- Evidence records per episode: 5
- Note: Gemini service-port mismatch had one initial read timeout; retry after client timeout/certifi patch succeeded.

| Provider | Problem | Status | Seconds | Diagnosis | Action | Submitted | Expected | Error/Note |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- |
| claude | native_bad_image_productcatalogservice | candidate | 7.156 | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| claude | native_service_port_mismatch_productcatalogservice | candidate | 6.96 | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| claude | native_cpu_limit_throttle_checkoutservice | candidate | 6.94 | True | True | native_cpu_limit_throttle/patch_resources | native_cpu_limit_throttle/patch_resources |  |
| claude | native_dependency_bad_endpoint_frontend_cartservice | candidate | 8.07 | False | False | native_bad_env/patch_resources | native_dependency_bad_endpoint/rollout_undo |  |
| claude | native_bad_env_checkoutservice_email | candidate | 7.806 | False | False | native_dependency_bad_endpoint/wait_and_monitor | native_bad_env/rollout_undo |  |
| openai | native_bad_image_productcatalogservice | candidate | 4.094 | True | False | native_bad_image/restart_pod | native_bad_image_rollout/rollout_undo |  |
| openai | native_service_port_mismatch_productcatalogservice | candidate | 4.353 | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| openai | native_cpu_limit_throttle_checkoutservice | candidate | 3.998 | False | False | native_memory_limit_oom/restart_pod | native_cpu_limit_throttle/patch_resources |  |
| openai | native_dependency_bad_endpoint_frontend_cartservice | candidate | 4.345 | True | False | native_dependency_bad_endpoint/wait_and_monitor | native_dependency_bad_endpoint/rollout_undo |  |
| openai | native_bad_env_checkoutservice_email | candidate | 12.564 | False | False | native_bad_probe/restart_pod | native_bad_env/rollout_undo |  |
| gemini | native_bad_image_productcatalogservice | candidate | 15.289 | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| gemini | native_service_port_mismatch_productcatalogservice | error | 30.316 | None | None | None/None | None/ | The read operation timed out |
| gemini | native_cpu_limit_throttle_checkoutservice | candidate | 12.649 | True | False | native_cpu_limit_throttle/rollout_undo | native_cpu_limit_throttle/patch_resources |  |
| gemini | native_dependency_bad_endpoint_frontend_cartservice | candidate | 11.009 | False | True | native_bad_env/rollout_undo | native_dependency_bad_endpoint/rollout_undo |  |
| gemini | native_bad_env_checkoutservice_email | candidate | 16.025 | False | False | native_dependency_bad_endpoint/rollout_restart | native_bad_env/rollout_undo |  |
| gemini_retry_timeoutfix | native_service_port_mismatch_productcatalogservice | candidate | 35.873 | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port | retry after timeout/certifi client fix |

## Provider Totals

| Provider | Runs | Completed | Diagnosis Correct | Action Correct | Avg Seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| claude | 5 | 5 | 3 | 3 | 7.386 |
| openai | 5 | 5 | 3 | 1 | 5.871 |
| gemini | 5 | 4 | 2 | 2 | 17.058 |

## Gemini Retry After Client Fix

| Problem | Diagnosis | Action | Submitted |
| --- | --- | --- | --- |
| native_service_port_mismatch_productcatalogservice | True | True | native_service_port_mismatch/patch_service_target_port |
