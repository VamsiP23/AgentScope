# Reproducibility Guide

This repo is set up so another human or agent can do three things without reconstructing the project history:

1. inspect the committed benchmark dataset
2. regenerate the paper/report figures from committed analysis inputs
3. rerun benchmark variants over the committed replay dataset

## 1. Environment

From the repo root:

```bash
cd /Users/aarnavsawant/Documents/CS6365/AgentScope
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Provider-backed replay reruns also need the relevant API key in the environment.

## 2. Verify What Is Committed

Dataset manifest:

- [`configs/episode_sets/native_50.yaml`](/Users/aarnavsawant/Documents/CS6365/AgentScope/configs/episode_sets/native_50.yaml)

Taxonomy:

- [`configs/episode_taxonomy.yaml`](/Users/aarnavsawant/Documents/CS6365/AgentScope/configs/episode_taxonomy.yaml)

Committed replay dataset root:

- [`datasets/episodes`](/Users/aarnavsawant/Documents/CS6365/AgentScope/datasets/episodes)

Committed analysis inputs used by the report:

- [`results/analysis`](/Users/aarnavsawant/Documents/CS6365/AgentScope/results/analysis)

Quick dataset count check:

```bash
python3 - <<'PY'
from pathlib import Path
import yaml
root = Path('/Users/aarnavsawant/Documents/CS6365/AgentScope')
payload = yaml.safe_load((root / 'configs/episode_sets/native_50.yaml').read_text())
print(payload['name'], len(payload['episodes']))
PY
```

Expected output:

```text
native_48_strict_good 48
```

## 3. Regenerate Report Figures

The figures in the report can be regenerated from the committed analysis JSON without rerunning models:

```bash
python3 scripts/generate_report_figures.py
```

Outputs:

- [`results/analysis/figures/figure_main_model_comparison.png`](/Users/aarnavsawant/Documents/CS6365/AgentScope/results/analysis/figures/figure_main_model_comparison.png)
- [`results/analysis/figures/figure_category_breakdown.png`](/Users/aarnavsawant/Documents/CS6365/AgentScope/results/analysis/figures/figure_category_breakdown.png)
- [`results/analysis/figures/figure_runtime_vs_accuracy.png`](/Users/aarnavsawant/Documents/CS6365/AgentScope/results/analysis/figures/figure_runtime_vs_accuracy.png)
- [`results/analysis/figures/figure_agent_architectures.png`](/Users/aarnavsawant/Documents/CS6365/AgentScope/results/analysis/figures/figure_agent_architectures.png)

## 4. Rerun The Replay Benchmark

Use the committed replay suite runner:

```bash
python3 scripts/run_replay_suite.py \
  --episode-set configs/episode_sets/native_50.yaml \
  --variant compact_one_shot \
  --provider anthropic \
  --model claude-sonnet-4-0
```

Useful variants:

- `compact_one_shot`
- `structured_compact`
- `generic_react`
- `bounded_react`
- `diagnostic`

This creates a new run directory under `results/replay_runs/` with:

- `run_summary.json`
- `aggregate_results.json`
- `aggregate_results.md`
- per-episode `agent_report.json`
- per-episode `evaluation.json`

For a cheap sanity run:

```bash
python3 scripts/run_replay_suite.py \
  --episode-set configs/episode_sets/native_50.yaml \
  --variant bounded_react \
  --provider anthropic \
  --model claude-sonnet-4-0 \
  --limit 5
```

## 5. Reproduce A Single Case Study

Compact one-shot:

```bash
python3 scripts/run_compact_diagnosis.py \
  --replay-dataset datasets/episodes/native_bad_image_productcatalogservice/native_bad_image_productcatalogservice_001.json \
  --provider anthropic \
  --model claude-sonnet-4-0 \
  --out-dir results/replay_runs/repro_bad_image_case
```

Bounded ReAct:

```bash
python3 scripts/run_benchmark_agent.py \
  --agent-type bounded_react \
  --backend replay \
  --replay-dataset datasets/episodes/native_dependency_bad_endpoint_frontend_cartservice/native_dependency_bad_endpoint_frontend_cartservice_005.json \
  --benchmark-suite benchmark_suite.yaml \
  --problem-id native_dependency_bad_endpoint_frontend_cartservice \
  --provider anthropic \
  --model claude-sonnet-4-0 \
  --out-file results/replay_runs/repro_dependency_case/agent_report.json
```

## 6. Run The Live Demo

The live demo is intentionally separate from the reproducible replay benchmark. To run it:

```bash
zsh -lic 'cd /Users/aarnavsawant/Documents/CS6365/AgentScope && ./scripts/run_live_fix_demo.sh'
```

This requires:

- a working Kubernetes cluster
- the Online Boutique app
- the observability stack
- `ANTHROPIC_API_KEY`

Setup instructions are in [`observability/README.md`](/Users/aarnavsawant/Documents/CS6365/AgentScope/observability/README.md).

## 7. Tests

```bash
pytest tests
```

The tests cover:

- evidence distillation
- taxonomy grouping
- evaluator partial credit
- compact diagnosis behavior
- bounded/diagnostic agent helpers

## 8. What Not To Rely On

Do not treat `experiment_runs/` as the benchmark reproduction surface. Those directories are useful for demos and local debugging, but the reproducible benchmark contract is:

- episode manifests in `configs/episode_sets/`
- episode JSONs in `datasets/episodes/`
- benchmark problem metadata in `benchmark_suite.yaml`
- replay runners in `scripts/`
- analysis inputs in `results/analysis/`
