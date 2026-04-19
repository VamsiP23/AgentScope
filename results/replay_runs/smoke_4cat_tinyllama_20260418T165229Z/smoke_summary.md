# TinyLlama Four-Category Smoke

- Run root: `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/replay_runs/smoke_4cat_tinyllama_20260418T165229Z`
- Agent: compact one-shot
- Evidence records: 5

| Category | Status | Time | Diagnosis | Action | Submitted | Expected |
| --- | --- | ---: | --- | --- | --- | --- |
| availability_rollout | evaluated | 29.533 | False | False | /patch_service_selector | native_bad_image_rollout/rollout_undo |
| service_wiring_configuration | evaluated | 8.916 | False | False | / | native_service_port_mismatch/patch_service_target_port |
| resource_performance | error | 90.346 |  |  | timed out/ | / |
| dependency_path_trace_centered | evaluated | 7.218 | False | False | / | native_dependency_bad_endpoint/rollout_undo |
