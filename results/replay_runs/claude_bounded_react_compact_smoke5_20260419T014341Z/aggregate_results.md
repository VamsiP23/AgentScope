# Benchmark Aggregate Results

- Runs: 5

## Diagnosis Category

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| availability_rollout | 2 | 0.5 | 0.5 | 0.5 | 1.0 | 4.5 | 208.75 |
| dependency_path_trace_centered | 1 | 0.0 | 0.0 | 0.0 | 1.0 | 4.0 | 175.437 |
| resource_performance | 1 | 1.0 | 1.0 | 1.0 | 1.0 | 4.0 | 131.094 |
| service_wiring_configuration | 1 | 1.0 | 1.0 | 1.0 | 1.0 | 2.0 | 72.127 |

## Difficulty

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| causal_path | 1 | 0.0 | 0.0 | 0.0 | 1.0 | 4.0 | 175.437 |
| contrast_required | 2 | 1.0 | 1.0 | 1.0 | 1.0 | 3.0 | 101.611 |
| direct_signal | 2 | 0.5 | 0.5 | 0.5 | 1.0 | 4.5 | 208.75 |

## Trace Required

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| trace_not_required | 4 | 0.75 | 0.75 | 0.75 | 1.0 | 3.75 | 155.18 |
| trace_required | 1 | 0.0 | 0.0 | 0.0 | 1.0 | 4.0 | 175.437 |

## Fault Family

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| native_bad_image_rollout | 1 | 1.0 | 1.0 | 1.0 | 1.0 | 4.0 | 210.399 |
| native_cpu_pressure_stress_job | 1 | 1.0 | 1.0 | 1.0 | 1.0 | 4.0 | 131.094 |
| native_dependency_bad_endpoint | 1 | 0.0 | 0.0 | 0.0 | 1.0 | 4.0 | 175.437 |
| native_pod_delete | 1 | 0.0 | 0.0 | 0.0 | 1.0 | 5.0 | 207.101 |
| native_service_port_mismatch | 1 | 1.0 | 1.0 | 1.0 | 1.0 | 2.0 | 72.127 |
