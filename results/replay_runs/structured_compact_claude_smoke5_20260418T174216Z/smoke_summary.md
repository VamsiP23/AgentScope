# Claude Structured Compact Smoke 5

- Run root: `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/replay_runs/structured_compact_claude_smoke5_20260418T174216Z`
- Manifest: `configs/episode_sets/smoke_5.yaml`
- Provider/model: `anthropic` / `claude-sonnet-4-20250514`

| Problem | Status | Seconds | Diagnosis | Action | Submitted | Expected | Error |
| --- | --- | ---: | --- | --- | --- | --- | --- |
| native_bad_image_productcatalogservice | candidate | 34.945 | True | True | native_bad_image_rollout/rollout_undo | native_bad_image_rollout/rollout_undo |  |
| native_service_port_mismatch_productcatalogservice | candidate | 26.619 | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |  |
| native_cpu_limit_throttle_checkoutservice | candidate | 36.356 | True | True | native_cpu_limit_throttle/patch_resources | native_cpu_limit_throttle/patch_resources |  |
| native_dependency_bad_endpoint_frontend_cartservice | candidate | 42.28 | False | False | native_bad_env/patch_resources | native_dependency_bad_endpoint/rollout_undo |  |
| native_bad_env_checkoutservice_email | candidate | 40.413 | False | False | native_dependency_bad_endpoint/patch_service_target_port | native_bad_env/rollout_undo |  |

## Totals

- Completed: 5/5
- Diagnosis correct: 3/5
- Action correct: 3/5
- Avg seconds: 36.123
