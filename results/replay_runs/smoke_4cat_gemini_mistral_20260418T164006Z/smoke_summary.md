# Gemini/Mistral Four-Category Smoke

- Run root: `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/replay_runs/smoke_4cat_gemini_mistral_20260418T164006Z`
- Agent: compact one-shot
- Evidence records: 5
- Note: results use evaluator aliases for legacy `native_bad_image` -> `native_bad_image_rollout` labels.

| Model | Category | Problem | Status | Diagnosis | Action | Submitted | Expected |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gemini-2.5-flash | availability_rollout | native_bad_image_productcatalogservice | evaluated | True | True | native_bad_image/rollout_undo | native_bad_image_rollout/rollout_undo |
| gemini-2.5-flash | service_wiring_configuration | native_service_port_mismatch_productcatalogservice | evaluated | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |
| gemini-2.5-flash | resource_performance | native_cpu_limit_throttle_checkoutservice | evaluated | True | True | native_cpu_limit_throttle/patch_resources | native_cpu_limit_throttle/patch_resources |
| gemini-2.5-flash | dependency_path_trace_centered | native_dependency_bad_endpoint_frontend_cartservice | evaluated | False | False | native_bad_env/patch_resources | native_dependency_bad_endpoint/rollout_undo |
| mistral:latest | availability_rollout | native_bad_image_productcatalogservice | evaluated | False | True | native_service_selector_mismatch/rollout_undo | native_bad_image_rollout/rollout_undo |
| mistral:latest | service_wiring_configuration | native_service_port_mismatch_productcatalogservice | evaluated | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |
| mistral:latest | resource_performance | native_cpu_limit_throttle_checkoutservice | evaluated | True | True | native_cpu_limit_throttle/patch_resources | native_cpu_limit_throttle/patch_resources |
| mistral:latest | dependency_path_trace_centered | native_dependency_bad_endpoint_frontend_cartservice | evaluated | False | False | native_service_port_mismatch/patch_service_target_port | native_dependency_bad_endpoint/rollout_undo |
