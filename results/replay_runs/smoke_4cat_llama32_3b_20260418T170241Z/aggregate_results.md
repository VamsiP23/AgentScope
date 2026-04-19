# Benchmark Aggregate Results

- Runs: 4

## Diagnosis Category

| key | runs | diagnosis_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- |
| availability_rollout | 1 | 0.0 | 0.0 | 1.0 | 5.0 | 0.005 |
| dependency_path_trace_centered | 1 | 1.0 | 0.0 | 1.0 | 5.0 | 0.005 |
| resource_performance | 1 | 0.0 | 0.0 | 1.0 | 5.0 | 0.005 |
| service_wiring_configuration | 1 | 1.0 | 1.0 | 1.0 | 5.0 | 0.005 |

## Difficulty

| key | runs | diagnosis_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- |
| causal_path | 1 | 1.0 | 0.0 | 1.0 | 5.0 | 0.005 |
| contrast_required | 2 | 0.5 | 0.5 | 1.0 | 5.0 | 0.005 |
| direct_signal | 1 | 0.0 | 0.0 | 1.0 | 5.0 | 0.005 |

## Trace Required

| key | runs | diagnosis_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- |
| trace_not_required | 3 | 0.333 | 0.333 | 1.0 | 5.0 | 0.005 |
| trace_required | 1 | 1.0 | 0.0 | 1.0 | 5.0 | 0.005 |

## Fault Family

| key | runs | diagnosis_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- |
| native_bad_image_rollout | 1 | 0.0 | 0.0 | 1.0 | 5.0 | 0.005 |
| native_cpu_limit_throttle | 1 | 0.0 | 0.0 | 1.0 | 5.0 | 0.005 |
| native_dependency_bad_endpoint | 1 | 1.0 | 0.0 | 1.0 | 5.0 | 0.005 |
| native_service_port_mismatch | 1 | 1.0 | 1.0 | 1.0 | 5.0 | 0.005 |
