# Benchmark Aggregate Results

- Runs: 8

## Diagnosis Category

| key | runs | diagnosis_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- |
| availability_rollout | 2 | 0.5 | 1.0 | 1.0 | 5.0 | 0.005 |
| dependency_path_trace_centered | 2 | 0.0 | 0.0 | 1.0 | 5.0 | 0.005 |
| resource_performance | 2 | 1.0 | 1.0 | 1.0 | 5.0 | 0.005 |
| service_wiring_configuration | 2 | 1.0 | 1.0 | 1.0 | 5.0 | 0.005 |

## Difficulty

| key | runs | diagnosis_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- |
| causal_path | 2 | 0.0 | 0.0 | 1.0 | 5.0 | 0.005 |
| contrast_required | 4 | 1.0 | 1.0 | 1.0 | 5.0 | 0.005 |
| direct_signal | 2 | 0.5 | 1.0 | 1.0 | 5.0 | 0.005 |

## Trace Required

| key | runs | diagnosis_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- |
| trace_not_required | 6 | 0.833 | 1.0 | 1.0 | 5.0 | 0.005 |
| trace_required | 2 | 0.0 | 0.0 | 1.0 | 5.0 | 0.005 |

## Fault Family

| key | runs | diagnosis_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- |
| native_bad_image_rollout | 2 | 0.5 | 1.0 | 1.0 | 5.0 | 0.005 |
| native_cpu_limit_throttle | 2 | 1.0 | 1.0 | 1.0 | 5.0 | 0.005 |
| native_dependency_bad_endpoint | 2 | 0.0 | 0.0 | 1.0 | 5.0 | 0.005 |
| native_service_port_mismatch | 2 | 1.0 | 1.0 | 1.0 | 5.0 | 0.005 |
