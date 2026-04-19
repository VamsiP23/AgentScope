# Dependency-Grouped Results

Canonical dependency label: `native_dependency_config_regression`.
Legacy submissions `native_bad_env` and `native_dependency_bad_endpoint` are scored as aliases for this canonical label.

## Headline

| Run | Setting | Episodes | Exact | Family | Action | Avg runtime sec | Avg evidence/tool records |
|---|---:|---:|---:|---:|---:|---:|---:|
| Claude one-shot | compact_one_shot | 48 | 41/48 (85.4%) | 41/48 (85.4%) | 41/48 (85.4%) | 7.907 | 6.71 |
| OpenAI GPT-4o one-shot | compact_one_shot | 48 | 39/48 (81.2%) | 39/48 (81.2%) | 40/48 (83.3%) | 6.929 | 6.71 |
| OpenAI GPT-4o-mini one-shot | compact_one_shot | 48 | 36/48 (75.0%) | 36/48 (75.0%) | 27/48 (56.2%) | 4.296 | 6.71 |
| Gemini one-shot | compact_one_shot | 48 | 42/48 (87.5%) | 42/48 (87.5%) | 40/48 (83.3%) | 14.113 | 6.71 |
| Claude Bounded ReAct | bounded_react | 48 | 34/48 (70.8%) | 34/48 (70.8%) | 35/48 (72.9%) | 178.933 | 3.92 |
| Claude DiagnosticAgent dependency10 | diagnostic_agent | 10 | 5/10 (50.0%) | 5/10 (50.0%) | 6/10 (60.0%) | 32.807 | 6.7 |

## Category Breakdown

| Run | Category | Episodes | Exact | Family | Action |
|---|---|---:|---:|---:|---:|
| Claude one-shot | availability_rollout | 17 | 14/17 (82.4%) | 14/17 (82.4%) | 13/17 (76.5%) |
| Claude one-shot | dependency_path_trace_centered | 10 | 7/10 (70.0%) | 7/10 (70.0%) | 7/10 (70.0%) |
| Claude one-shot | resource_performance | 11 | 10/11 (90.9%) | 10/11 (90.9%) | 11/11 (100.0%) |
| Claude one-shot | service_wiring_configuration | 10 | 10/10 (100.0%) | 10/10 (100.0%) | 10/10 (100.0%) |
| OpenAI GPT-4o one-shot | availability_rollout | 17 | 13/17 (76.5%) | 13/17 (76.5%) | 12/17 (70.6%) |
| OpenAI GPT-4o one-shot | dependency_path_trace_centered | 10 | 7/10 (70.0%) | 7/10 (70.0%) | 8/10 (80.0%) |
| OpenAI GPT-4o one-shot | resource_performance | 11 | 9/11 (81.8%) | 9/11 (81.8%) | 10/11 (90.9%) |
| OpenAI GPT-4o one-shot | service_wiring_configuration | 10 | 10/10 (100.0%) | 10/10 (100.0%) | 10/10 (100.0%) |
| OpenAI GPT-4o-mini one-shot | availability_rollout | 17 | 12/17 (70.6%) | 12/17 (70.6%) | 13/17 (76.5%) |
| OpenAI GPT-4o-mini one-shot | dependency_path_trace_centered | 10 | 6/10 (60.0%) | 6/10 (60.0%) | 1/10 (10.0%) |
| OpenAI GPT-4o-mini one-shot | resource_performance | 11 | 8/11 (72.7%) | 8/11 (72.7%) | 7/11 (63.6%) |
| OpenAI GPT-4o-mini one-shot | service_wiring_configuration | 10 | 10/10 (100.0%) | 10/10 (100.0%) | 6/10 (60.0%) |
| Gemini one-shot | availability_rollout | 17 | 13/17 (76.5%) | 13/17 (76.5%) | 13/17 (76.5%) |
| Gemini one-shot | dependency_path_trace_centered | 10 | 9/10 (90.0%) | 9/10 (90.0%) | 7/10 (70.0%) |
| Gemini one-shot | resource_performance | 11 | 10/11 (90.9%) | 10/11 (90.9%) | 10/11 (90.9%) |
| Gemini one-shot | service_wiring_configuration | 10 | 10/10 (100.0%) | 10/10 (100.0%) | 10/10 (100.0%) |
| Claude Bounded ReAct | availability_rollout | 17 | 12/17 (70.6%) | 12/17 (70.6%) | 13/17 (76.5%) |
| Claude Bounded ReAct | dependency_path_trace_centered | 10 | 2/10 (20.0%) | 2/10 (20.0%) | 1/10 (10.0%) |
| Claude Bounded ReAct | resource_performance | 11 | 10/11 (90.9%) | 10/11 (90.9%) | 11/11 (100.0%) |
| Claude Bounded ReAct | service_wiring_configuration | 10 | 10/10 (100.0%) | 10/10 (100.0%) | 10/10 (100.0%) |

## Dependency Slice

| Run | Episodes | Exact | Family | Action | Predicted labels |
|---|---:|---:|---:|---:|---|
| Claude one-shot | 10 | 7/10 (70.0%) | 7/10 (70.0%) | 7/10 (70.0%) | native_bad_env: 1, native_bad_probe_rollout: 1, native_cpu_limit_throttle: 1, native_dependency_bad_endpoint: 6, native_scale_zero: 1 |
| OpenAI GPT-4o one-shot | 10 | 7/10 (70.0%) | 7/10 (70.0%) | 8/10 (80.0%) | native_bad_env: 3, native_bad_probe: 1, native_cpu_limit_throttle: 1, native_dependency_bad_endpoint: 4, native_pod_delete: 1 |
| OpenAI GPT-4o-mini one-shot | 10 | 6/10 (60.0%) | 6/10 (60.0%) | 1/10 (10.0%) | native_bad_probe: 3, native_dependency_bad_endpoint: 6, native_memory_pressure_stress_job: 1 |
| Gemini one-shot | 10 | 9/10 (90.0%) | 9/10 (90.0%) | 7/10 (70.0%) | native_bad_env: 3, native_cpu_limit_throttle: 1, native_dependency_bad_endpoint: 6 |
| Claude Bounded ReAct | 10 | 2/10 (20.0%) | 2/10 (20.0%) | 1/10 (10.0%) | native_bad_env: 2, native_bad_probe_rollout: 4, native_cpu_limit_throttle: 1, native_dependency_bad_endpoint: 1, native_memory_limit_oom: 1, pod_disturbance: 1 |
| Claude DiagnosticAgent dependency10 | 10 | 5/10 (50.0%) | 5/10 (50.0%) | 6/10 (60.0%) | native_bad_env: 3, native_bad_probe_rollout: 1, native_cpu_limit_throttle: 1, native_dependency_bad_endpoint: 4, native_pod_delete: 1 |
