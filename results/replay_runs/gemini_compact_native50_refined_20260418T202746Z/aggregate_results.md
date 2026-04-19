# Benchmark Aggregate Results

- Runs: 50

## Diagnosis Category

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| availability_rollout | 18 | 0.778 | 0.778 | 0.778 | 1.0 | 5.889 | 0.006 |
| dependency_path_trace_centered | 10 | 0.2 | 0.8 | 0.8 | 1.0 | 8.0 | 0.008 |
| resource_performance | 12 | 0.333 | 0.333 | 0.417 | 1.0 | 6.75 | 0.007 |
| service_wiring_configuration | 10 | 1.0 | 1.0 | 1.0 | 1.0 | 6.4 | 0.006 |

## Difficulty

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| causal_path | 10 | 0.2 | 0.8 | 0.8 | 1.0 | 8.0 | 0.008 |
| contrast_required | 22 | 0.636 | 0.636 | 0.682 | 1.0 | 6.591 | 0.007 |
| direct_signal | 18 | 0.778 | 0.778 | 0.778 | 1.0 | 5.889 | 0.006 |

## Trace Required

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| trace_not_required | 40 | 0.7 | 0.7 | 0.725 | 1.0 | 6.275 | 0.006 |
| trace_required | 10 | 0.2 | 0.8 | 0.8 | 1.0 | 8.0 | 0.008 |

## Fault Family

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| native_bad_env | 5 | 0.0 | 0.6 | 0.6 | 1.0 | 8.0 | 0.008 |
| native_bad_image_rollout | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 7.0 | 0.007 |
| native_bad_probe_rollout | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 4.6 | 0.005 |
| native_cpu_limit_throttle | 3 | 0.667 | 0.667 | 0.667 | 1.0 | 8.0 | 0.008 |
| native_cpu_pressure_stress_job | 3 | 0.0 | 0.0 | 0.0 | 1.0 | 6.0 | 0.006 |
| native_dependency_bad_endpoint | 5 | 0.4 | 1.0 | 1.0 | 1.0 | 8.0 | 0.008 |
| native_memory_limit_oom | 3 | 0.667 | 0.667 | 1.0 | 1.0 | 8.0 | 0.008 |
| native_memory_pressure_stress_job | 3 | 0.0 | 0.0 | 0.0 | 1.0 | 5.0 | 0.005 |
| native_pod_delete | 5 | 0.2 | 0.2 | 0.2 | 1.0 | 5.8 | 0.006 |
| native_scale_zero | 3 | 1.0 | 1.0 | 1.0 | 1.0 | 6.333 | 0.006 |
| native_service_port_mismatch | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 6.4 | 0.006 |
| native_service_selector_mismatch | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 6.4 | 0.006 |
