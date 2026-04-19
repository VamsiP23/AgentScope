# Benchmark Aggregate Results

- Runs: 45

## Diagnosis Category

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| availability_rollout | 17 | 0.588 | 0.588 | 0.588 | 1.0 | 8.0 | 0.008 |
| dependency_path_trace_centered | 9 | 0.111 | 0.444 | 0.667 | 1.0 | 10.0 | 0.01 |
| resource_performance | 9 | 0.333 | 0.333 | 0.333 | 1.0 | 8.778 | 0.009 |
| service_wiring_configuration | 10 | 1.0 | 1.0 | 1.0 | 1.0 | 8.4 | 0.008 |

## Difficulty

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| causal_path | 9 | 0.111 | 0.444 | 0.667 | 1.0 | 10.0 | 0.01 |
| contrast_required | 19 | 0.684 | 0.684 | 0.684 | 1.0 | 8.579 | 0.009 |
| direct_signal | 17 | 0.588 | 0.588 | 0.588 | 1.0 | 8.0 | 0.008 |

## Trace Required

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| trace_not_required | 36 | 0.639 | 0.639 | 0.639 | 1.0 | 8.306 | 0.008 |
| trace_required | 9 | 0.111 | 0.444 | 0.667 | 1.0 | 10.0 | 0.01 |

## Fault Family

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| native_bad_env | 5 | 0.0 | 0.2 | 0.6 | 1.0 | 10.0 | 0.01 |
| native_bad_image_rollout | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 9.0 | 0.009 |
| native_bad_probe_rollout | 4 | 1.0 | 1.0 | 1.0 | 1.0 | 6.75 | 0.007 |
| native_cpu_limit_throttle | 2 | 1.0 | 1.0 | 1.0 | 1.0 | 10.0 | 0.01 |
| native_cpu_pressure_stress_job | 3 | 0.0 | 0.0 | 0.0 | 1.0 | 8.0 | 0.008 |
| native_dependency_bad_endpoint | 4 | 0.25 | 0.75 | 0.75 | 1.0 | 10.0 | 0.01 |
| native_memory_limit_oom | 2 | 0.5 | 0.5 | 0.5 | 1.0 | 10.0 | 0.01 |
| native_memory_pressure_stress_job | 2 | 0.0 | 0.0 | 0.0 | 1.0 | 7.5 | 0.007 |
| native_pod_delete | 5 | 0.0 | 0.0 | 0.0 | 1.0 | 7.8 | 0.008 |
| native_scale_zero | 3 | 0.333 | 0.333 | 0.333 | 1.0 | 8.333 | 0.008 |
| native_service_port_mismatch | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 8.4 | 0.008 |
| native_service_selector_mismatch | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 8.4 | 0.008 |
