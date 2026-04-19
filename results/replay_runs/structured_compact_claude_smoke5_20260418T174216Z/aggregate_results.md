# Benchmark Aggregate Results

- Runs: 5

## Diagnosis Category

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| availability_rollout | 1 | 1.0 | 1.0 | 1.0 | 1.0 | 9.0 | 0.009 |
| dependency_path_trace_centered | 2 | 0.0 | 0.5 | 0.0 | 1.0 | 10.0 | 0.01 |
| resource_performance | 1 | 1.0 | 1.0 | 1.0 | 1.0 | 10.0 | 0.01 |
| service_wiring_configuration | 1 | 1.0 | 1.0 | 1.0 | 1.0 | 9.0 | 0.009 |

## Difficulty

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| causal_path | 2 | 0.0 | 0.5 | 0.0 | 1.0 | 10.0 | 0.01 |
| contrast_required | 2 | 1.0 | 1.0 | 1.0 | 1.0 | 9.5 | 0.009 |
| direct_signal | 1 | 1.0 | 1.0 | 1.0 | 1.0 | 9.0 | 0.009 |

## Trace Required

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| trace_not_required | 3 | 1.0 | 1.0 | 1.0 | 1.0 | 9.333 | 0.009 |
| trace_required | 2 | 0.0 | 0.5 | 0.0 | 1.0 | 10.0 | 0.01 |

## Fault Family

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| native_bad_env | 1 | 0.0 | 0.0 | 0.0 | 1.0 | 10.0 | 0.01 |
| native_bad_image_rollout | 1 | 1.0 | 1.0 | 1.0 | 1.0 | 9.0 | 0.009 |
| native_cpu_limit_throttle | 1 | 1.0 | 1.0 | 1.0 | 1.0 | 10.0 | 0.01 |
| native_dependency_bad_endpoint | 1 | 0.0 | 1.0 | 0.0 | 1.0 | 10.0 | 0.01 |
| native_service_port_mismatch | 1 | 1.0 | 1.0 | 1.0 | 1.0 | 9.0 | 0.009 |
