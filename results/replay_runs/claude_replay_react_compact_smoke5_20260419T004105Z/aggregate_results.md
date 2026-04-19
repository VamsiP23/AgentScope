# Benchmark Aggregate Results

- Runs: 5

## Diagnosis Category

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| availability_rollout | 2 | 0.5 | 0.5 | 0.5 | 1.0 | 3.0 | 132.942 |
| dependency_path_trace_centered | 1 | 0.0 | 0.0 | 0.0 | 1.0 | 3.0 | 107.357 |
| resource_performance | 1 | 0.0 | 0.0 | 0.0 | 1.0 | 6.0 | 208.321 |
| service_wiring_configuration | 1 | 1.0 | 1.0 | 1.0 | 1.0 | 2.0 | 68.283 |

## Difficulty

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| causal_path | 1 | 0.0 | 0.0 | 0.0 | 1.0 | 3.0 | 107.357 |
| contrast_required | 2 | 0.5 | 0.5 | 0.5 | 1.0 | 4.0 | 138.302 |
| direct_signal | 2 | 0.5 | 0.5 | 0.5 | 1.0 | 3.0 | 132.942 |

## Trace Required

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| trace_not_required | 4 | 0.5 | 0.5 | 0.5 | 1.0 | 3.5 | 135.622 |
| trace_required | 1 | 0.0 | 0.0 | 0.0 | 1.0 | 3.0 | 107.357 |

## Fault Family

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| native_bad_image_rollout | 1 | 1.0 | 1.0 | 1.0 | 1.0 | 2.0 | 63.435 |
| native_cpu_pressure_stress_job | 1 | 0.0 | 0.0 | 0.0 | 1.0 | 6.0 | 208.321 |
| native_dependency_bad_endpoint | 1 | 0.0 | 0.0 | 0.0 | 1.0 | 3.0 | 107.357 |
| native_pod_delete | 1 | 0.0 | 0.0 | 0.0 | 1.0 | 4.0 | 202.45 |
| native_service_port_mismatch | 1 | 1.0 | 1.0 | 1.0 | 1.0 | 2.0 | 68.283 |
