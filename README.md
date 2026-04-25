# AgentScope

AgentScope is a benchmark and live-demo framework for AI-assisted incident diagnosis on the Online Boutique microservice application. The repo contains:

- a committed replay dataset under [`datasets/episodes`](/Users/aarnavsawant/Documents/CS6365/AgentScope/datasets/episodes)
- benchmark metadata under [`benchmark_suite.yaml`](/Users/aarnavsawant/Documents/CS6365/AgentScope/benchmark_suite.yaml)
- scored replay runs and paper-ready analysis under [`results`](/Users/aarnavsawant/Documents/CS6365/AgentScope/results)
- a native Kubernetes live demo path under [`scripts/run_live_fix_demo.sh`](/Users/aarnavsawant/Documents/CS6365/AgentScope/scripts/run_live_fix_demo.sh)

If you only need the shortest path:

1. read [`REPRODUCIBILITY.md`](/Users/aarnavsawant/Documents/CS6365/AgentScope/REPRODUCIBILITY.md)
2. regenerate the paper figures with `python3 scripts/generate_report_figures.py`
3. rerun a replay benchmark with `python3 scripts/run_replay_suite.py ...`

## Repository Layout

- [`benchmark_suite.yaml`](/Users/aarnavsawant/Documents/CS6365/AgentScope/benchmark_suite.yaml): benchmark problem definitions, scoring expectations, and live experiment mappings
- [`configs/episode_sets/native_50.yaml`](/Users/aarnavsawant/Documents/CS6365/AgentScope/configs/episode_sets/native_50.yaml): committed `native_48_strict_good` replay manifest
- [`configs/episode_taxonomy.yaml`](/Users/aarnavsawant/Documents/CS6365/AgentScope/configs/episode_taxonomy.yaml): category, difficulty, and trace-requirement labels used in grouped analysis
- [`datasets/README.md`](/Users/aarnavsawant/Documents/CS6365/AgentScope/datasets/README.md): dataset structure and what is committed
- [`scripts/run_replay_suite.py`](/Users/aarnavsawant/Documents/CS6365/AgentScope/scripts/run_replay_suite.py): rerun replay benchmarks over a committed episode set
- [`scripts/run_compact_diagnosis.py`](/Users/aarnavsawant/Documents/CS6365/AgentScope/scripts/run_compact_diagnosis.py): one-shot compact replay diagnosis for one episode
- [`scripts/run_structured_compact_diagnosis.py`](/Users/aarnavsawant/Documents/CS6365/AgentScope/scripts/run_structured_compact_diagnosis.py): structured compact replay diagnosis for one episode
- [`scripts/run_benchmark_agent.py`](/Users/aarnavsawant/Documents/CS6365/AgentScope/scripts/run_benchmark_agent.py): generic replay/live entrypoint for ReAct, bounded ReAct, and DiagnosticAgent
- [`scripts/run_experiment.py`](/Users/aarnavsawant/Documents/CS6365/AgentScope/scripts/run_experiment.py): live bounded experiment runner
- [`scripts/aggregate_results.py`](/Users/aarnavsawant/Documents/CS6365/AgentScope/scripts/aggregate_results.py): aggregate `evaluation.json` files into markdown/json summaries
- [`scripts/generate_report_figures.py`](/Users/aarnavsawant/Documents/CS6365/AgentScope/scripts/generate_report_figures.py): regenerate the charts used in the report

## Reproduce The Paper Artifacts

All committed analysis inputs already live in [`results/analysis`](/Users/aarnavsawant/Documents/CS6365/AgentScope/results/analysis), so regenerating the figures does not require rerunning the expensive benchmark:

```bash
cd /Users/aarnavsawant/Documents/CS6365/AgentScope
python3 scripts/generate_report_figures.py
```

This writes:

- [`results/analysis/figures/figure_main_model_comparison.png`](/Users/aarnavsawant/Documents/CS6365/AgentScope/results/analysis/figures/figure_main_model_comparison.png)
- [`results/analysis/figures/figure_category_breakdown.png`](/Users/aarnavsawant/Documents/CS6365/AgentScope/results/analysis/figures/figure_category_breakdown.png)
- [`results/analysis/figures/figure_runtime_vs_accuracy.png`](/Users/aarnavsawant/Documents/CS6365/AgentScope/results/analysis/figures/figure_runtime_vs_accuracy.png)
- [`results/analysis/figures/figure_agent_architectures.png`](/Users/aarnavsawant/Documents/CS6365/AgentScope/results/analysis/figures/figure_agent_architectures.png)

## Rerun Replay Benchmarks

The committed replay dataset is the reproducible benchmark surface. The simplest rerun path is:

```bash
cd /Users/aarnavsawant/Documents/CS6365/AgentScope
python3 scripts/run_replay_suite.py \
  --episode-set configs/episode_sets/native_50.yaml \
  --variant compact_one_shot \
  --provider anthropic \
  --model claude-sonnet-4-0
```

Other useful variants:

- `compact_one_shot`
- `structured_compact`
- `generic_react`
- `bounded_react`
- `diagnostic`

Each replay suite run writes a new directory under `results/replay_runs/` containing:

- `run_summary.json`
- `aggregate_results.json`
- `aggregate_results.md`
- one subdirectory per episode with `agent_report.json` and `evaluation.json`

For a smaller smoke rerun, add `--limit 5`.

## Run One Replay Episode

Compact one-shot on a single committed episode:

```bash
python3 scripts/run_compact_diagnosis.py \
  --replay-dataset datasets/episodes/native_bad_image_productcatalogservice/native_bad_image_productcatalogservice_001.json \
  --provider anthropic \
  --model claude-sonnet-4-0 \
  --out-dir results/replay_runs/manual_bad_image_one_shot
```

Bounded ReAct on a single committed episode:

```bash
python3 scripts/run_benchmark_agent.py \
  --agent-type bounded_react \
  --backend replay \
  --replay-dataset datasets/episodes/native_bad_env_checkoutservice_email/native_bad_env_checkoutservice_email_005.json \
  --benchmark-suite benchmark_suite.yaml \
  --problem-id native_bad_env_checkoutservice_email \
  --provider anthropic \
  --model claude-sonnet-4-0 \
  --out-file results/replay_runs/manual_bad_env_bounded/agent_report.json
```

## Run The Live Demo

The presentation-friendly native live demo is:

```bash
zsh -lic 'cd /Users/aarnavsawant/Documents/CS6365/AgentScope && ./scripts/run_live_fix_demo.sh'
```

This expects:

- a working Kubernetes cluster with Online Boutique deployed
- observability endpoints available
- `ANTHROPIC_API_KEY` in the shell environment

See [`observability/README.md`](/Users/aarnavsawant/Documents/CS6365/AgentScope/observability/README.md) for the local stack setup.

## Tests

Run the focused test suite with:

```bash
cd /Users/aarnavsawant/Documents/CS6365/AgentScope
pytest tests
```

## Notes On What Is Committed

- the replay dataset is committed
- the benchmark metadata and taxonomy are committed
- the scored replay results and report-analysis inputs are committed
- large live-run artifact directories under `experiment_runs/` are not part of the reproducibility contract

For a cold-start grader, [`REPRODUCIBILITY.md`](/Users/aarnavsawant/Documents/CS6365/AgentScope/REPRODUCIBILITY.md) is the best place to begin.
