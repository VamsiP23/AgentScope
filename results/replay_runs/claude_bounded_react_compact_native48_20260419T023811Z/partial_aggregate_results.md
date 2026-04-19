# Benchmark Aggregate Results

- Runs: 23

## Diagnosis Category

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| availability_rollout | 13 | 0.923 | 0.923 | 0.923 | 1.0 | 3.769 | 181.693 |
| service_wiring_configuration | 10 | 1.0 | 1.0 | 1.0 | 1.0 | 2.3 | 101.147 |

## Difficulty

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| contrast_required | 10 | 1.0 | 1.0 | 1.0 | 1.0 | 2.3 | 101.147 |
| direct_signal | 13 | 0.923 | 0.923 | 0.923 | 1.0 | 3.769 | 181.693 |

## Trace Required

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| trace_not_required | 23 | 0.957 | 0.957 | 0.957 | 1.0 | 3.13 | 146.673 |

## Fault Family

| key | runs | diagnosis_accuracy | diagnosis_family_accuracy | action_accuracy | valid_submission_rate | avg_tool_calls_to_solution | avg_time_to_diagnosis_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| native_bad_image_rollout | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 3.4 | 164.564 |
| native_bad_probe_rollout | 5 | 0.8 | 0.8 | 0.8 | 1.0 | 4.2 | 199.05 |
| native_scale_zero | 3 | 1.0 | 1.0 | 1.0 | 1.0 | 3.667 | 181.311 |
| native_service_port_mismatch | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 2.0 | 79.169 |
| native_service_selector_mismatch | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 2.6 | 123.125 |
