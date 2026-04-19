# Llama 3.2 3B Four-Category Smoke

- Run root: `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/replay_runs/smoke_4cat_llama32_3b_20260418T170241Z`
- Agent: compact one-shot
- Provider/model: `ollama` / `llama3.2:3b`
- Evidence records: 5

| Category | Problem | Status | Seconds | Diagnosis | Action | Submitted | Expected |
| --- | --- | ---: | ---: | --- | --- | --- | --- |
| availability_rollout | native_bad_image_productcatalogservice | candidate | 18.231 | False | False | native_service_selector_mismatch/patch_service_selector | native_bad_image_rollout/rollout_undo |
| service_wiring_configuration | native_service_port_mismatch_productcatalogservice | candidate | 13.883 | True | True | native_service_port_mismatch/patch_service_target_port | native_service_port_mismatch/patch_service_target_port |
| resource_performance | native_cpu_limit_throttle_checkoutservice | candidate | 10.501 | False | False | / | native_cpu_limit_throttle/patch_resources |
| dependency_path_trace_centered | native_dependency_bad_endpoint_frontend_cartservice | candidate | 16.137 | True | False | native_dependency_bad_endpoint/wait_and_monitor | native_dependency_bad_endpoint/rollout_undo |
