# Ollama Llama 3.2 3B Compact Native48

- Run root: `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/replay_runs/ollama_llama32_3b_compact_native48_20260419T191820Z`
- Generated: 2026-04-19T20:02:03Z
- Model: `llama3.2:3b` via Ollama

## Headline

| Episodes | Completed | Errors/timeouts | Exact | Grouped family | Action | Avg seconds |
|---:|---:|---:|---:|---:|---:|---:|
| 48 | 46/48 (95.8%) | 2/48 | 6/46 (13.0%) | 6/46 (13.0%) | 4/46 (8.7%) | 48.856 |

## Category Breakdown

| Category | Episodes | Completed | Exact | Grouped family | Action | Avg seconds |
|---|---:|---:|---:|---:|---:|---:|
| availability_rollout | 17 | 16/17 | 1/16 (6.2%) | 1/16 (6.2%) | 1/16 (6.2%) | 46.662 |
| dependency_path_trace_centered | 10 | 10/10 | 0/10 (0.0%) | 0/10 (0.0%) | 0/10 (0.0%) | 43.732 |
| resource_performance | 11 | 11/11 | 0/11 (0.0%) | 0/11 (0.0%) | 0/11 (0.0%) | 46.84 |
| service_wiring_configuration | 10 | 9/10 | 5/9 (55.6%) | 5/9 (55.6%) | 3/9 (33.3%) | 59.929 |

## Family Breakdown

| Family | Episodes | Completed | Exact | Grouped family | Action | Avg seconds |
|---|---:|---:|---:|---:|---:|---:|
| native_bad_env | 5 | 5/5 | 0/5 (0.0%) | 0/5 (0.0%) | 0/5 (0.0%) | 39.006 |
| native_bad_image_rollout | 5 | 5/5 | 0/5 (0.0%) | 0/5 (0.0%) | 0/5 (0.0%) | 49.082 |
| native_bad_probe_rollout | 5 | 4/5 | 1/4 (25.0%) | 1/4 (25.0%) | 1/4 (25.0%) | 59.712 |
| native_cpu_limit_throttle | 3 | 3/3 | 0/3 (0.0%) | 0/3 (0.0%) | 0/3 (0.0%) | 39.217 |
| native_cpu_pressure_stress_job | 3 | 3/3 | 0/3 (0.0%) | 0/3 (0.0%) | 0/3 (0.0%) | 49.53 |
| native_dependency_bad_endpoint | 5 | 5/5 | 0/5 (0.0%) | 0/5 (0.0%) | 0/5 (0.0%) | 48.458 |
| native_memory_limit_oom | 2 | 2/2 | 0/2 (0.0%) | 0/2 (0.0%) | 0/2 (0.0%) | 41.845 |
| native_memory_pressure_stress_job | 3 | 3/3 | 0/3 (0.0%) | 0/3 (0.0%) | 0/3 (0.0%) | 55.104 |
| native_pod_delete | 4 | 4/4 | 0/4 (0.0%) | 0/4 (0.0%) | 0/4 (0.0%) | 34.196 |
| native_scale_zero | 3 | 3/3 | 0/3 (0.0%) | 0/3 (0.0%) | 0/3 (0.0%) | 37.5 |
| native_service_port_mismatch | 5 | 5/5 | 1/5 (20.0%) | 1/5 (20.0%) | 0/5 (0.0%) | 51.933 |
| native_service_selector_mismatch | 5 | 4/5 | 4/4 (100.0%) | 4/4 (100.0%) | 3/4 (75.0%) | 67.925 |

## Non-completions

| Episode | Status | Error | Seconds |
|---|---|---|---:|
| native_service_selector_mismatch_cartservice_004 | error | {   "timestamp_utc": "2026-04-19T19:27:58Z",   "provider": "ollama",   "model": "llama3.2:3b",   "replay_dataset": "/Users/aarnavsawant/Documents/CS6365/AgentScope/datasets/episodes/native_service_selector_mismatch_carts | 181.74 |
| native_bad_probe_cartservice_004 | error | {   "timestamp_utc": "2026-04-19T19:37:46Z",   "provider": "ollama",   "model": "llama3.2:3b",   "replay_dataset": "/Users/aarnavsawant/Documents/CS6365/AgentScope/datasets/episodes/native_bad_probe_cartservice/native_ba | 181.809 |

## Readout

- This is a feasible local baseline, but not a competitive diagnostic baseline.
- The model completed most episodes but timed out twice through the local Ollama API.
- Accuracy is much lower than hosted frontier models even with the same compact distilled evidence.
- Use this as evidence that local small models are attractive operationally but currently weak for this benchmark.
