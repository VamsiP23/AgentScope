# Benchmark Aggregate Results

- Runs: 30

## Diagnosis Category

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| availability_rollout | 18 | 0.722 | 0.722 | 0.722 | 1.0 | 7.889 | 0.008 |
| dependency_path_trace_centered | 2 | 0.0 | 1.0 | 1.0 | 1.0 | 10.0 | 0.01 |
| service_wiring_configuration | 10 | 1.0 | 1.0 | 1.0 | 1.0 | 8.4 | 0.008 |

## Difficulty

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| causal_path | 2 | 0.0 | 1.0 | 1.0 | 1.0 | 10.0 | 0.01 |
| contrast_required | 10 | 1.0 | 1.0 | 1.0 | 1.0 | 8.4 | 0.008 |
| direct_signal | 18 | 0.722 | 0.722 | 0.722 | 1.0 | 7.889 | 0.008 |

## Trace Required

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| trace_not_required | 28 | 0.821 | 0.821 | 0.821 | 1.0 | 8.071 | 0.008 |
| trace_required | 2 | 0.0 | 1.0 | 1.0 | 1.0 | 10.0 | 0.01 |

## Fault Family

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| native_bad_image_rollout | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 9.0 | 0.009 |
| native_bad_probe_rollout | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 6.6 | 0.007 |
| native_dependency_bad_endpoint | 2 | 0.0 | 1.0 | 1.0 | 1.0 | 10.0 | 0.01 |
| native_pod_delete | 5 | 0.0 | 0.0 | 0.0 | 1.0 | 7.8 | 0.008 |
| native_scale_zero | 3 | 1.0 | 1.0 | 1.0 | 1.0 | 8.333 | 0.008 |
| native_service_port_mismatch | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 8.4 | 0.008 |
| native_service_selector_mismatch | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 8.4 | 0.008 |
