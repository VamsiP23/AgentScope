# Hosted Compact One-Shot Native-50 Comparison

Setting: compact one-shot replay over the same `native_50` episode set.

Runs:
- Claude: `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/replay_runs/claude_compact_native50_refined_20260418T200116Z`
- OpenAI: `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/replay_runs/openai_compact_native50_refined_20260418T201827Z`
- Gemini: `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/replay_runs/gemini_compact_native50_refined_20260418T202746Z`

## Overall Results

| Model | Provider/model | Completed | Exact diagnosis | Family diagnosis | Action correct | Avg runtime |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Claude | Claude compact run | 50/50 | 33/50 (66%) | 37/50 (74%) | 39/50 (78%) | 8.752s |
| OpenAI | `gpt-4o-mini` | 50/50 | 32/50 (64%) | 34/50 (68%) | 28/50 (56%) | 4.163s |
| Gemini | `gemini-2.5-flash` | 50/50 | 30/50 (60%) | 36/50 (72%) | 37/50 (74%) | 14.889s |

## Category Results

| Model | Category | Episodes | Exact diagnosis | Family diagnosis | Action correct |
| --- | --- | ---: | ---: | ---: | ---: |
| Claude | Availability & rollout | 18 | 15/18 (83.3%) | 15/18 (83.3%) | 15/18 (83.3%) |
| Claude | Service wiring & configuration | 10 | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) |
| Claude | Resource & performance | 12 | 5/12 (41.7%) | 5/12 (41.7%) | 6/12 (50.0%) |
| Claude | Dependency-path / trace-centered | 10 | 3/10 (30.0%) | 7/10 (70.0%) | 8/10 (80.0%) |
| OpenAI | Availability & rollout | 18 | 13/18 (72.2%) | 13/18 (72.2%) | 12/18 (66.7%) |
| OpenAI | Service wiring & configuration | 10 | 10/10 (100%) | 10/10 (100%) | 6/10 (60.0%) |
| OpenAI | Resource & performance | 12 | 4/12 (33.3%) | 4/12 (33.3%) | 4/12 (33.3%) |
| OpenAI | Dependency-path / trace-centered | 10 | 5/10 (50.0%) | 7/10 (70.0%) | 6/10 (60.0%) |
| Gemini | Availability & rollout | 18 | 14/18 (77.8%) | 14/18 (77.8%) | 14/18 (77.8%) |
| Gemini | Service wiring & configuration | 10 | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) |
| Gemini | Resource & performance | 12 | 4/12 (33.3%) | 4/12 (33.3%) | 5/12 (41.7%) |
| Gemini | Dependency-path / trace-centered | 10 | 2/10 (20.0%) | 8/10 (80.0%) | 8/10 (80.0%) |

## Trace-Required Subset

| Model | Episodes | Exact diagnosis | Family diagnosis | Action correct |
| --- | ---: | ---: | ---: | ---: |
| Claude | 10 | 3/10 (30%) | 7/10 (70%) | 8/10 (80%) |
| OpenAI | 10 | 5/10 (50%) | 7/10 (70%) | 6/10 (60%) |
| Gemini | 10 | 2/10 (20%) | 8/10 (80%) | 8/10 (80%) |

## Interpretation

Claude is the strongest overall compact one-shot baseline: best exact diagnosis, best family diagnosis, best action accuracy, and moderate latency.

OpenAI is the fastest by a wide margin and nearly matches Claude on exact diagnosis, but action selection is much weaker. This makes it a good throughput baseline, not the best final diagnosis system.

Gemini is the slowest and slightly weaker on exact diagnosis, but it produces strong action choices and high family-level performance on trace-required episodes. Its dependency failures are often fine-grained label confusions rather than fully wrong remediations.

The most stable benchmark slice is service wiring/configuration: all three models reach 10/10 exact diagnosis. The weakest slice remains resource/performance, especially stress-job cases where the packaged replay evidence does not expose a clean active stress workload signal.

