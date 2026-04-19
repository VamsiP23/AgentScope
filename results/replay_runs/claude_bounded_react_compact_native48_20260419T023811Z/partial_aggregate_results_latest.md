# Benchmark Aggregate Results

- Runs: 29

## Diagnosis Category

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| availability_rollout | 17 | 0.706 | 0.706 | 0.765 | 1.0 | 4.059 | 184.943 |
| dependency_path_trace_centered | 2 | 0.0 | 0.0 | 0.0 | 1.0 | 6.0 | 242.25 |
| service_wiring_configuration | 10 | 1.0 | 1.0 | 1.0 | 1.0 | 2.3 | 101.147 |

## Difficulty

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| causal_path | 2 | 0.0 | 0.0 | 0.0 | 1.0 | 6.0 | 242.25 |
| contrast_required | 10 | 1.0 | 1.0 | 1.0 | 1.0 | 2.3 | 101.147 |
| direct_signal | 17 | 0.706 | 0.706 | 0.765 | 1.0 | 4.059 | 184.943 |

## Trace Required

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| trace_not_required | 27 | 0.815 | 0.815 | 0.852 | 1.0 | 3.407 | 153.907 |
| trace_required | 2 | 0.0 | 0.0 | 0.0 | 1.0 | 6.0 | 242.25 |

## Fault Family

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| native_bad_image_rollout | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 3.4 | 164.564 |
| native_bad_probe_rollout | 5 | 0.8 | 0.8 | 0.8 | 1.0 | 4.2 | 199.05 |
| native_dependency_bad_endpoint | 2 | 0.0 | 0.0 | 0.0 | 1.0 | 6.0 | 242.25 |
| native_pod_delete | 4 | 0.0 | 0.0 | 0.25 | 1.0 | 5.0 | 195.506 |
| native_scale_zero | 3 | 1.0 | 1.0 | 1.0 | 1.0 | 3.667 | 181.311 |
| native_service_port_mismatch | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 2.0 | 79.169 |
| native_service_selector_mismatch | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 2.6 | 123.125 |
