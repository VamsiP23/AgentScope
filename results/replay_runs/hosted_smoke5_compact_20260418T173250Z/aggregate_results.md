# Benchmark Aggregate Results

- Runs: 15

## Diagnosis Category

| key | runs | diagnosis_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- |
| availability_rollout | 3 | 1.0 | 0.667 | 1.0 | 5.0 | 0.005 |
| dependency_path_trace_centered | 6 | 0.167 | 0.167 | 1.0 | 5.0 | 0.005 |
| resource_performance | 3 | 0.667 | 0.333 | 1.0 | 5.0 | 0.005 |
| service_wiring_configuration | 3 | 1.0 | 1.0 | 1.0 | 5.0 | 0.005 |

## Difficulty

| key | runs | diagnosis_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- |
| causal_path | 6 | 0.167 | 0.167 | 1.0 | 5.0 | 0.005 |
| contrast_required | 6 | 0.833 | 0.667 | 1.0 | 5.0 | 0.005 |
| direct_signal | 3 | 1.0 | 0.667 | 1.0 | 5.0 | 0.005 |

## Trace Required

| key | runs | diagnosis_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- |
| trace_not_required | 9 | 0.889 | 0.667 | 1.0 | 5.0 | 0.005 |
| trace_required | 6 | 0.167 | 0.167 | 1.0 | 5.0 | 0.005 |

## Fault Family

| key | runs | diagnosis_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- |
| native_bad_env | 3 | 0.0 | 0.0 | 1.0 | 5.0 | 0.005 |
| native_bad_image_rollout | 3 | 1.0 | 0.667 | 1.0 | 5.0 | 0.005 |
| native_cpu_limit_throttle | 3 | 0.667 | 0.333 | 1.0 | 5.0 | 0.005 |
| native_dependency_bad_endpoint | 3 | 0.333 | 0.333 | 1.0 | 5.0 | 0.005 |
| native_service_port_mismatch | 3 | 1.0 | 1.0 | 1.0 | 5.0 | 0.005 |
