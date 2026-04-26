# AgentScope

AgentScope is a benchmark and live-demo framework for AI-assisted incident diagnosis on the Online Boutique microservice application. The repo contains:

- a committed replay dataset under [`datasets/episodes`](datasets/episodes)
- benchmark metadata under [`benchmark_suite.yaml`](benchmark_suite.yaml)
- the final scored replay runs and paper-ready analysis under [`results`](results)
- a native Kubernetes live demo path under [`scripts/run_live_fix_demo.sh`](scripts/run_live_fix_demo.sh)

If you only need the shortest path:

1. read [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md)
2. regenerate the paper figures with `python3 scripts/generate_report_figures.py`
3. rerun a replay benchmark with `python3 scripts/run_replay_suite.py ...`

In the commands below, replace `<repo-root>` with the directory where you cloned this repository.

## Fast Start

If you want the fastest cold-start path from clone to a working run:

```bash
cd <repo-root>
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export ANTHROPIC_API_KEY=your_key_here

python3 scripts/generate_report_figures.py

python3 scripts/run_replay_suite.py \
  --episode-set configs/episode_sets/native_50.yaml \
  --variant compact_one_shot \
  --provider anthropic \
  --model claude-sonnet-4-0 \
  --limit 5
```

That sequence is enough to verify the repo installs, the committed analysis regenerates, and the replay benchmark path works.

## Repository Layout

- [`benchmark_suite.yaml`](benchmark_suite.yaml): benchmark problem definitions, scoring expectations, and live experiment mappings
- [`configs/episode_sets/native_50.yaml`](configs/episode_sets/native_50.yaml): committed `native_48_strict_good` replay manifest
- [`configs/episode_taxonomy.yaml`](configs/episode_taxonomy.yaml): category, difficulty, and trace-requirement labels used in grouped analysis
- [`datasets/README.md`](datasets/README.md): dataset structure and what is committed
- [`scripts/run_replay_suite.py`](scripts/run_replay_suite.py): rerun replay benchmarks over a committed episode set
- [`scripts/run_compact_diagnosis.py`](scripts/run_compact_diagnosis.py): one-shot compact replay diagnosis for one episode
- [`scripts/run_structured_compact_diagnosis.py`](scripts/run_structured_compact_diagnosis.py): structured compact replay diagnosis for one episode
- [`scripts/run_benchmark_agent.py`](scripts/run_benchmark_agent.py): generic replay/live entrypoint for ReAct, bounded ReAct, and DiagnosticAgent
- [`scripts/run_experiment.py`](scripts/run_experiment.py): live bounded experiment runner
- [`scripts/aggregate_results.py`](scripts/aggregate_results.py): aggregate `evaluation.json` files into markdown/json summaries
- [`scripts/generate_report_figures.py`](scripts/generate_report_figures.py): regenerate the charts used in the report

## LLM Provider Setup

The code supports these hosted providers for replay/live runs:

- `anthropic` -> `ANTHROPIC_API_KEY`
- `openai` -> `OPENAI_API_KEY`
- `gemini` -> `GEMINI_API_KEY`

Copy-paste setup examples:

```bash
export ANTHROPIC_API_KEY=your_key_here
export OPENAI_API_KEY=your_key_here
export GEMINI_API_KEY=your_key_here
```

If you only plan to use Claude, you only need:

```bash
export ANTHROPIC_API_KEY=your_key_here
```

Optional model overrides are also supported:

```bash
export ANTHROPIC_MODEL=claude-sonnet-4-0
export OPENAI_MODEL=gpt-4o
export GEMINI_MODEL=gemini-2.5-flash
```

If you want these keys loaded automatically in future shells, add the relevant `export ...` line to `~/.zshrc` or `~/.zprofile`, then open a new shell or run `source ~/.zshrc`.

## Reproduce The Paper Artifacts

All committed analysis inputs already live in [`results/analysis`](results/analysis), so regenerating the figures does not require rerunning the expensive benchmark:

```bash
cd <repo-root>
python3 scripts/generate_report_figures.py
```

This writes:

- [`results/analysis/figures/figure_main_model_comparison.png`](results/analysis/figures/figure_main_model_comparison.png)
- [`results/analysis/figures/figure_category_breakdown.png`](results/analysis/figures/figure_category_breakdown.png)
- [`results/analysis/figures/figure_runtime_vs_accuracy.png`](results/analysis/figures/figure_runtime_vs_accuracy.png)
- [`results/analysis/figures/figure_agent_architectures.png`](results/analysis/figures/figure_agent_architectures.png)

## Rerun Replay Benchmarks

The committed replay dataset is the reproducible benchmark surface. The simplest rerun path is:

```bash
cd <repo-root>
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

If the command exits with an error like `ANTHROPIC_API_KEY is not set`, the provider key is missing from your current shell.

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
zsh -lic 'cd <repo-root> && ./scripts/run_live_fix_demo.sh'
```

This expects:

- a working Kubernetes cluster with Online Boutique deployed
- observability endpoints available
- `ANTHROPIC_API_KEY` in the shell environment

See [`observability/README.md`](observability/README.md) for the local stack setup.

## Tests

Run the focused test suite with:

```bash
cd <repo-root>
pytest tests
```

If `pytest` is not found, make sure the virtual environment from the setup step is activated:

```bash
source .venv/bin/activate
```

## Notes On What Is Committed

- the replay dataset is committed
- the benchmark metadata and taxonomy are committed
- the final scored replay results and report-analysis inputs used by the report are committed
- one successful live-demo artifact directory is committed under [`experiment_runs/20260425T175830Z_native_bad_image_productcatalogservice_live_demo`](experiment_runs/20260425T175830Z_native_bad_image_productcatalogservice_live_demo)
- older exploratory live-run and replay-run history has been intentionally pruned so the repo stays focused on the benchmark and demo surfaces described above

For a cold-start grader, [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) is the best place to begin.
