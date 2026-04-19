# Claude ReAct Agent Comparison

All three runs use Claude Sonnet 4.0 on `native_48_strict_good` with compact replay evidence/tools.

## Headline

| Agent | Episodes | Exact | Grouped family | Action | Avg seconds | Avg tool/evidence calls | Avg repeated calls |
|---|---:|---:|---:|---:|---:|---:|---:|
| Generic ReAct | 48 | 27/48 (56.2%) | 27/48 (56.2%) | 26/48 (54.2%) | 142.27 | 3.5 | 0.0 |
| Bounded ReAct | 48 | 33/48 (68.8%) | 34/48 (70.8%) | 35/48 (72.9%) | 178.933 | 3.92 | 0.0 |
| DiagnosticAgent | 48 | 32/48 (66.7%) | 36/48 (75.0%) | 36/48 (75.0%) | 186.451 | 6.17 | 0.04 |

## Category Breakdown

| Category | Generic E/F/A | Bounded E/F/A | Diagnostic E/F/A |
|---|---:|---:|---:|
| availability_rollout | 12/17 / 12/17 / 10/17 | 12/17 / 12/17 / 13/17 | 13/17 / 13/17 / 13/17 |
| dependency_path_trace_centered | 0/10 / 0/10 / 1/10 | 1/10 / 2/10 / 1/10 | 2/10 / 6/10 / 6/10 |
| resource_performance | 5/11 / 5/11 / 5/11 | 10/11 / 10/11 / 11/11 | 7/11 / 7/11 / 7/11 |
| service_wiring_configuration | 10/10 / 10/10 / 10/10 | 10/10 / 10/10 / 10/10 | 10/10 / 10/10 / 10/10 |

## Family Breakdown

| Family | Generic E/F/A | Bounded E/F/A | Diagnostic E/F/A |
|---|---:|---:|---:|
| native_bad_env | 0/5 / 0/5 / 1/5 | 1/5 / 1/5 / 0/5 | 0/5 / 1/5 / 1/5 |
| native_bad_image_rollout | 5/5 / 5/5 / 5/5 | 5/5 / 5/5 / 5/5 | 5/5 / 5/5 / 5/5 |
| native_bad_probe_rollout | 4/5 / 4/5 / 2/5 | 4/5 / 4/5 / 4/5 | 5/5 / 5/5 / 5/5 |
| native_cpu_limit_throttle | 3/3 / 3/3 / 3/3 | 3/3 / 3/3 / 3/3 | 3/3 / 3/3 / 3/3 |
| native_cpu_pressure_stress_job | 0/3 / 0/3 / 0/3 | 3/3 / 3/3 / 3/3 | 0/3 / 0/3 / 0/3 |
| native_dependency_bad_endpoint | 0/5 / 0/5 / 0/5 | 0/5 / 1/5 / 1/5 | 2/5 / 5/5 / 5/5 |
| native_memory_limit_oom | 2/2 / 2/2 / 2/2 | 1/2 / 1/2 / 2/2 | 2/2 / 2/2 / 2/2 |
| native_memory_pressure_stress_job | 0/3 / 0/3 / 0/3 | 3/3 / 3/3 / 3/3 | 2/3 / 2/3 / 2/3 |
| native_pod_delete | 0/4 / 0/4 / 0/4 | 0/4 / 0/4 / 1/4 | 0/4 / 0/4 / 0/4 |
| native_scale_zero | 3/3 / 3/3 / 3/3 | 3/3 / 3/3 / 3/3 | 3/3 / 3/3 / 3/3 |
| native_service_port_mismatch | 5/5 / 5/5 / 5/5 | 5/5 / 5/5 / 5/5 | 5/5 / 5/5 / 5/5 |
| native_service_selector_mismatch | 5/5 / 5/5 / 5/5 | 5/5 / 5/5 / 5/5 | 5/5 / 5/5 / 5/5 |

## Readout

- Generic ReAct is the weakest overall of the three replay agents on strict/family/action metrics.
- Generic ReAct solves service wiring, bad image, scale-zero, CPU-limit, and memory-OOM cases cleanly.
- Generic ReAct fails all retained pod-delete, dependency-path, and stress-job cases, which makes it a useful pure baseline for the paper.
- DiagnosticAgent is the best of the three on dependency-path family/action accuracy, while Bounded ReAct is strongest on resource/stress-job cases.
