# AgentScope

AgentScope is an episodic benchmark for distributed-systems failure diagnosis with observability-aware agents.

The project evaluates how well different agent architectures and LLM backbones diagnose injected failures in a live microservice environment or against replayed benchmark episodes. Each task is a bounded failure-diagnosis episode with a fixed interaction budget, explicit ground truth, and automatic scoring.

## Benchmark vs Demo

AgentScope has two intended modes:

- `benchmark`: reproducible episodic evaluation for comparing agents and models
- `demo`: a presentation-friendly live run that shows one agent investigating one active fault

Benchmark mode is the primary methodology. Demo mode exists to make the system tangible.

## Core Loop

Each benchmark episode follows the same structure:

1. inject one fault into the Online Boutique environment
2. let the agent inspect the system through observability tools
3. require a diagnosis and remediation recommendation within a fixed budget
4. score the result against task ground truth
5. reset and repeat

This preserves realism while keeping evaluation controlled enough to compare architectures, prompts, and model backbones fairly.

## Repository Map

- [benchmark_suite.yaml](/Users/aarnavsawant/Documents/CS6365/AgentScope/benchmark_suite.yaml): full benchmark task catalog with ground truth and telemetry contracts
- [configs/core_suite.yaml](/Users/aarnavsawant/Documents/CS6365/AgentScope/configs/core_suite.yaml): initial frozen core suite for benchmark runs
- [scripts/run_experiment.py](/Users/aarnavsawant/Documents/CS6365/AgentScope/scripts/run_experiment.py): runs one bounded live episode
- [scripts/run_benchmark_suite.py](/Users/aarnavsawant/Documents/CS6365/AgentScope/scripts/run_benchmark_suite.py): runs a suite of episodes and aggregates results
- [scripts/run_replay_suite.py](/Users/aarnavsawant/Documents/CS6365/AgentScope/scripts/run_replay_suite.py): runs replay benchmarking over curated episodes in `datasets/episodes/`
- [scripts/run_benchmark_agent.py](/Users/aarnavsawant/Documents/CS6365/AgentScope/scripts/run_benchmark_agent.py): agent-only benchmark entrypoint
- [scripts/collect_episode.py](/Users/aarnavsawant/Documents/CS6365/AgentScope/scripts/collect_episode.py): collects a benchmark episode from the live system without running an agent
- [scripts/promote_episode.py](/Users/aarnavsawant/Documents/CS6365/AgentScope/scripts/promote_episode.py): promotes a live `episode.json` run into the curated benchmark dataset
- [benchmarking/evaluator.py](/Users/aarnavsawant/Documents/CS6365/AgentScope/benchmarking/evaluator.py): scoring logic
- [benchmarking/results.py](/Users/aarnavsawant/Documents/CS6365/AgentScope/benchmarking/results.py): aggregate evaluation utilities
- [experiments/README.md](/Users/aarnavsawant/Documents/CS6365/AgentScope/experiments/README.md): fault scenario and experiment configuration guidance
- [agent_graph/README.md](/Users/aarnavsawant/Documents/CS6365/AgentScope/agent_graph/README.md): current reference agent implementation

## Environment

The default live environment uses:

- Online Boutique microservices
- Prometheus
- Jaeger
- kube-state-metrics
- Native Kubernetes fault injection implemented in this repository

Setup details are in [observability/README.md](/Users/aarnavsawant/Documents/CS6365/AgentScope/observability/README.md).

## Running One Benchmark Episode

Run a single bounded live episode:

```bash
python3 ./scripts/run_experiment.py experiments/bad_rollout_productcatalogservice_react.yaml
```

The run writes artifacts under `experiment_runs/<timestamp>_<name>/`, including:

- `episode.json`
- `summary.json`
- `agent_report.json`
- `evaluation.json`
- tool logs and telemetry validation output

## Running The Core Benchmark Suite

Run the initial frozen suite:

```bash
python3 ./scripts/run_benchmark_suite.py --suite-file configs/core_suite.yaml
```

Optional model overrides:

```bash
python3 ./scripts/run_benchmark_suite.py \
  --suite-file configs/core_suite.yaml \
  --provider ollama \
  --model qwen2.5:7b \
  --compact-local-mode true
```

The suite runner writes:

- episode run artifacts under `results/benchmark_runs/<timestamp>/runs/`
- `aggregate_results.json`
- `aggregate_results.md`

You can also use named presets:

```bash
python3 ./scripts/run_benchmark_suite.py \
  --suite-file configs/core_suite.yaml \
  --model-config ollama_qwen_demo \
  --agent-config react_compact_local
```

## Curating Episodes

The default collection path does not require an agent. It runs a bounded live evidence probe, converts the collected tool outputs into a replayable benchmark episode, and promotes it into the curated dataset:

```bash
python3 ./scripts/collect_episode.py experiments/bad_rollout_productcatalogservice_react.yaml --copy-supporting
```

This writes raw collection artifacts under `results/episode_collection_runs/` and a curated benchmark episode under `datasets/episodes/`.

If you already have a raw run artifact and want to promote it manually, use:

```bash
python3 ./scripts/promote_episode.py <run_dir> --copy-supporting
```

Curated episodes live under [datasets/episodes](/Users/aarnavsawant/Documents/CS6365/AgentScope/datasets/episodes).

## Running Replay Benchmarking

Once curated episodes exist, run replay evaluation across them with:

```bash
python3 ./scripts/run_replay_suite.py \
  --suite-file configs/core_suite.yaml \
  --model-config ollama_qwen_demo \
  --agent-config react_compact_local
```

Replay runs write:

- replay run artifacts under `results/replay_runs/<timestamp>/runs/`
- `aggregate_results.json`
- `aggregate_results.md`

## Demo Mode

Demo mode is intentionally narrower than benchmark mode. For a live demo, prefer:

- rollout failure scenarios first
- lower step budgets
- compact local mode for Ollama-backed agents

Example:

```bash
LLM_PROVIDER=ollama \
OLLAMA_MODEL=qwen2.5:7b \
AGENTSCOPE_COMPACT_LOCAL_MODE=true \
python3 ./scripts/run_experiment.py experiments/bad_rollout_productcatalogservice_react.yaml
```

## Evaluation Methodology

AgentScope uses episodic evaluation over controlled failure-diagnosis tasks. Each episode begins with a known injected fault in a live microservice environment, after which an LLM agent is given bounded access to observability tools and must identify the root cause within a fixed interaction budget. This design preserves realism while enabling reproducible comparison across agent architectures and LLM backbones.

Primary benchmark metrics include:

- incident detected
- diagnosis correct
- action correct
- tool calls to solution
- time to diagnosis
- invalid submit count
- repeated call count
- evidence coverage

## Near-Term Roadmap

- improve the replay dataset conversion path and score richer episode metadata
- add named model and agent configs for easier cross-backbone comparisons
- expand the core suite once more scenarios become stable and benchmark-ready
