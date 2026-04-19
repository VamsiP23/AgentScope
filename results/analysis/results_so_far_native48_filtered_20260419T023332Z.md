# AgentScope Results So Far

Generated: `2026-04-19T02:33:32Z`

## Main Native-48 Compact One-Shot Results

These are filtered aggregates from the saved native-50 compact one-shot runs, with the two audited ambiguous episodes removed: `native_pod_delete_cartservice_003` and `native_memory_limit_oom_cartservice_001`. No model calls were rerun.

Strict set: `/Users/aarnavsawant/Documents/CS6365/AgentScope/configs/episode_sets/native_50.yaml` (`native_48_strict_good`, 48 episodes).

| Model | Run root | Completed | Exact | Family | Action | Avg wall seconds |
|---|---|---:|---:|---:|---:|---:|
| Claude Sonnet 4 (`claude-sonnet-4-0`) | `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/replay_runs/final_compact_native50_20260418T221253Z/claude_compact_native50_final` | 48/48 | 38/48 (79.2%) | 41/48 (85.4%) | 41/48 (85.4%) | 7.907 |
| OpenAI GPT-4o (`gpt-4o`) | `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/replay_runs/openai_gpt4o_compact_native50_final_20260419T000205Z` | 48/48 | 34/48 (70.8%) | 39/48 (81.2%) | 40/48 (83.3%) | 6.929 |
| OpenAI GPT-4o-mini (`gpt-4o-mini`) | `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/replay_runs/final_compact_native50_20260418T221253Z/openai_compact_native50_final` | 48/48 | 34/48 (70.8%) | 36/48 (75.0%) | 27/48 (56.2%) | 4.296 |
| Gemini 2.5 Flash (`gemini-2.5-flash`) | `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/replay_runs/final_compact_native50_20260418T221253Z/gemini_compact_native50_final` | 48/48 | 35/48 (72.9%) | 42/48 (87.5%) | 40/48 (83.3%) | 14.113 |

### Model Takeaways

- Best exact diagnosis: Claude Sonnet 4 with `38/48`.
- Best family-level diagnosis: Gemini 2.5 Flash with `42/48`.
- Best action accuracy: Claude Sonnet 4 with `41/48`.
- Fastest average response: OpenAI GPT-4o-mini at `4.296s`.

## Category Breakdown

| Model | Category | Episodes | Exact | Family | Action |
|---|---|---:|---:|---:|---:|
| Claude Sonnet 4 | Service wiring & configuration | 10 | 10/10 (100.0%) | 10/10 (100.0%) | 10/10 (100.0%) |
| Claude Sonnet 4 | Availability & rollout | 17 | 14/17 (82.4%) | 14/17 (82.4%) | 13/17 (76.5%) |
| Claude Sonnet 4 | Resource & performance | 11 | 10/11 (90.9%) | 10/11 (90.9%) | 11/11 (100.0%) |
| Claude Sonnet 4 | Dependency-path / trace-centered | 10 | 4/10 (40.0%) | 7/10 (70.0%) | 7/10 (70.0%) |
| OpenAI GPT-4o | Service wiring & configuration | 10 | 10/10 (100.0%) | 10/10 (100.0%) | 10/10 (100.0%) |
| OpenAI GPT-4o | Availability & rollout | 17 | 13/17 (76.5%) | 13/17 (76.5%) | 12/17 (70.6%) |
| OpenAI GPT-4o | Resource & performance | 11 | 9/11 (81.8%) | 9/11 (81.8%) | 10/11 (90.9%) |
| OpenAI GPT-4o | Dependency-path / trace-centered | 10 | 2/10 (20.0%) | 7/10 (70.0%) | 8/10 (80.0%) |
| OpenAI GPT-4o-mini | Service wiring & configuration | 10 | 10/10 (100.0%) | 10/10 (100.0%) | 6/10 (60.0%) |
| OpenAI GPT-4o-mini | Availability & rollout | 17 | 12/17 (70.6%) | 12/17 (70.6%) | 13/17 (76.5%) |
| OpenAI GPT-4o-mini | Resource & performance | 11 | 8/11 (72.7%) | 8/11 (72.7%) | 7/11 (63.6%) |
| OpenAI GPT-4o-mini | Dependency-path / trace-centered | 10 | 4/10 (40.0%) | 6/10 (60.0%) | 1/10 (10.0%) |
| Gemini 2.5 Flash | Service wiring & configuration | 10 | 10/10 (100.0%) | 10/10 (100.0%) | 10/10 (100.0%) |
| Gemini 2.5 Flash | Availability & rollout | 17 | 13/17 (76.5%) | 13/17 (76.5%) | 13/17 (76.5%) |
| Gemini 2.5 Flash | Resource & performance | 11 | 10/11 (90.9%) | 10/11 (90.9%) | 10/11 (90.9%) |
| Gemini 2.5 Flash | Dependency-path / trace-centered | 10 | 2/10 (20.0%) | 9/10 (90.0%) | 7/10 (70.0%) |

## Difficulty Breakdown

| Model | Difficulty | Episodes | Exact | Family | Action |
|---|---|---:|---:|---:|---:|
| Claude Sonnet 4 | direct_signal | 17 | 14/17 (82.4%) | 14/17 (82.4%) | 13/17 (76.5%) |
| Claude Sonnet 4 | contrast_required | 21 | 20/21 (95.2%) | 20/21 (95.2%) | 21/21 (100.0%) |
| Claude Sonnet 4 | causal_path | 10 | 4/10 (40.0%) | 7/10 (70.0%) | 7/10 (70.0%) |
| OpenAI GPT-4o | direct_signal | 17 | 13/17 (76.5%) | 13/17 (76.5%) | 12/17 (70.6%) |
| OpenAI GPT-4o | contrast_required | 21 | 19/21 (90.5%) | 19/21 (90.5%) | 20/21 (95.2%) |
| OpenAI GPT-4o | causal_path | 10 | 2/10 (20.0%) | 7/10 (70.0%) | 8/10 (80.0%) |
| OpenAI GPT-4o-mini | direct_signal | 17 | 12/17 (70.6%) | 12/17 (70.6%) | 13/17 (76.5%) |
| OpenAI GPT-4o-mini | contrast_required | 21 | 18/21 (85.7%) | 18/21 (85.7%) | 13/21 (61.9%) |
| OpenAI GPT-4o-mini | causal_path | 10 | 4/10 (40.0%) | 6/10 (60.0%) | 1/10 (10.0%) |
| Gemini 2.5 Flash | direct_signal | 17 | 13/17 (76.5%) | 13/17 (76.5%) | 13/17 (76.5%) |
| Gemini 2.5 Flash | contrast_required | 21 | 20/21 (95.2%) | 20/21 (95.2%) | 20/21 (95.2%) |
| Gemini 2.5 Flash | causal_path | 10 | 2/10 (20.0%) | 9/10 (90.0%) | 7/10 (70.0%) |

## Trace-Required Breakdown

| Model | Trace subset | Episodes | Exact | Family | Action |
|---|---|---:|---:|---:|---:|
| Claude Sonnet 4 | trace_required | 10 | 4/10 (40.0%) | 7/10 (70.0%) | 7/10 (70.0%) |
| Claude Sonnet 4 | trace_not_required | 38 | 34/38 (89.5%) | 34/38 (89.5%) | 34/38 (89.5%) |
| OpenAI GPT-4o | trace_required | 10 | 2/10 (20.0%) | 7/10 (70.0%) | 8/10 (80.0%) |
| OpenAI GPT-4o | trace_not_required | 38 | 32/38 (84.2%) | 32/38 (84.2%) | 32/38 (84.2%) |
| OpenAI GPT-4o-mini | trace_required | 10 | 4/10 (40.0%) | 6/10 (60.0%) | 1/10 (10.0%) |
| OpenAI GPT-4o-mini | trace_not_required | 38 | 30/38 (78.9%) | 30/38 (78.9%) | 26/38 (68.4%) |
| Gemini 2.5 Flash | trace_required | 10 | 2/10 (20.0%) | 9/10 (90.0%) | 7/10 (70.0%) |
| Gemini 2.5 Flash | trace_not_required | 38 | 33/38 (86.8%) | 33/38 (86.8%) | 33/38 (86.8%) |

## Fault-Family Breakdown

| Fault family | Episodes | Claude exact/family/action | GPT-4o exact/family/action | GPT-4o-mini exact/family/action | Gemini exact/family/action |
|---|---:|---:|---:|---:|---:|
| `native_service_port_mismatch` | 5 | 5/5 (100.0%) / 5/5 (100.0%) / 5/5 (100.0%) | 5/5 (100.0%) / 5/5 (100.0%) / 5/5 (100.0%) | 5/5 (100.0%) / 5/5 (100.0%) / 2/5 (40.0%) | 5/5 (100.0%) / 5/5 (100.0%) / 5/5 (100.0%) |
| `native_service_selector_mismatch` | 5 | 5/5 (100.0%) / 5/5 (100.0%) / 5/5 (100.0%) | 5/5 (100.0%) / 5/5 (100.0%) / 5/5 (100.0%) | 5/5 (100.0%) / 5/5 (100.0%) / 4/5 (80.0%) | 5/5 (100.0%) / 5/5 (100.0%) / 5/5 (100.0%) |
| `native_bad_image_rollout` | 5 | 5/5 (100.0%) / 5/5 (100.0%) / 5/5 (100.0%) | 5/5 (100.0%) / 5/5 (100.0%) / 5/5 (100.0%) | 5/5 (100.0%) / 5/5 (100.0%) / 5/5 (100.0%) | 5/5 (100.0%) / 5/5 (100.0%) / 5/5 (100.0%) |
| `native_bad_probe_rollout` | 5 | 5/5 (100.0%) / 5/5 (100.0%) / 3/5 (60.0%) | 1/5 (20.0%) / 1/5 (20.0%) / 0/5 (0.0%) | 1/5 (20.0%) / 1/5 (20.0%) / 1/5 (20.0%) | 5/5 (100.0%) / 5/5 (100.0%) / 5/5 (100.0%) |
| `native_scale_zero` | 3 | 3/3 (100.0%) / 3/3 (100.0%) / 3/3 (100.0%) | 3/3 (100.0%) / 3/3 (100.0%) / 3/3 (100.0%) | 3/3 (100.0%) / 3/3 (100.0%) / 3/3 (100.0%) | 3/3 (100.0%) / 3/3 (100.0%) / 3/3 (100.0%) |
| `native_pod_delete` | 4 | 1/4 (25.0%) / 1/4 (25.0%) / 2/4 (50.0%) | 4/4 (100.0%) / 4/4 (100.0%) / 4/4 (100.0%) | 3/4 (75.0%) / 3/4 (75.0%) / 4/4 (100.0%) | 0/4 (0.0%) / 0/4 (0.0%) / 0/4 (0.0%) |
| `native_dependency_bad_endpoint` | 5 | 4/5 (80.0%) / 5/5 (100.0%) / 5/5 (100.0%) | 2/5 (40.0%) / 5/5 (100.0%) / 5/5 (100.0%) | 4/5 (80.0%) / 4/5 (80.0%) / 1/5 (20.0%) | 2/5 (40.0%) / 5/5 (100.0%) / 5/5 (100.0%) |
| `native_bad_env` | 5 | 0/5 (0.0%) / 2/5 (40.0%) / 2/5 (40.0%) | 0/5 (0.0%) / 2/5 (40.0%) / 3/5 (60.0%) | 0/5 (0.0%) / 2/5 (40.0%) / 0/5 (0.0%) | 0/5 (0.0%) / 4/5 (80.0%) / 2/5 (40.0%) |
| `native_cpu_limit_throttle` | 3 | 3/3 (100.0%) / 3/3 (100.0%) / 3/3 (100.0%) | 2/3 (66.7%) / 2/3 (66.7%) / 2/3 (66.7%) | 3/3 (100.0%) / 3/3 (100.0%) / 0/3 (0.0%) | 2/3 (66.7%) / 2/3 (66.7%) / 2/3 (66.7%) |
| `native_memory_limit_oom` | 2 | 1/2 (50.0%) / 1/2 (50.0%) / 2/2 (100.0%) | 1/2 (50.0%) / 1/2 (50.0%) / 2/2 (100.0%) | 2/2 (100.0%) / 2/2 (100.0%) / 1/2 (50.0%) | 2/2 (100.0%) / 2/2 (100.0%) / 2/2 (100.0%) |
| `native_cpu_pressure_stress_job` | 3 | 3/3 (100.0%) / 3/3 (100.0%) / 3/3 (100.0%) | 3/3 (100.0%) / 3/3 (100.0%) / 3/3 (100.0%) | 3/3 (100.0%) / 3/3 (100.0%) / 3/3 (100.0%) | 3/3 (100.0%) / 3/3 (100.0%) / 3/3 (100.0%) |
| `native_memory_pressure_stress_job` | 3 | 3/3 (100.0%) / 3/3 (100.0%) / 3/3 (100.0%) | 3/3 (100.0%) / 3/3 (100.0%) / 3/3 (100.0%) | 0/3 (0.0%) / 0/3 (0.0%) / 3/3 (100.0%) | 3/3 (100.0%) / 3/3 (100.0%) / 3/3 (100.0%) |

## OpenAI Model Comparison

| Model | Exact | Family | Action | Avg seconds | Notes |
|---|---:|---:|---:|---:|---|
| `gpt-4o` | 34/48 (70.8%) | 39/48 (81.2%) | 40/48 (83.3%) | 6.929 | Better family/action; slightly slower than mini |
| `gpt-4o-mini` | 34/48 (70.8%) | 36/48 (75.0%) | 27/48 (56.2%) | 4.296 | Fastest, but weak action selection |

## Structured Compact Ablation

This is still a historical partial Claude structured compact run over the pre-filter native-50 manifest. It is useful as an architecture slice, but the main final table above is the cleaned native-48 compact one-shot benchmark.

| Setting | Episodes | Exact | Family | Action | Artifact |
|---|---:|---:|---:|---:|---|
| Claude structured compact partial | 30/50 historical | 23/30 (76.7%) | 25/30 (83.3%) | 25/30 (83.3%) | `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/replay_runs/claude_structured_compact_native50_final_20260418T232301Z` |
| Claude compact one-shot on same 30 | 30/50 historical | 25/30 (83.3%) | 26/30 (86.7%) | 25/30 (83.3%) | final compact Claude run |

## Current Interpretation

- The main final table should now be compact one-shot over `native_48_strict_good`, with Claude, GPT-4o, GPT-4o-mini, and Gemini.
- The two removed episodes should be described as audited exclusions, not model failures.
- Service wiring remains saturated and should be framed as a competency-floor/control category.
- Dependency-path exact labels remain the hardest: models often get family/action right but confuse `native_bad_env` and `native_dependency_bad_endpoint`.
- Stress-job evidence is now fairer after `get_cluster_resource_context`; Claude, GPT-4o, and Gemini solve those families cleanly.
- Pod-delete/lifecycle remains a hard boundary even after removing the most ambiguous pod-delete case.
