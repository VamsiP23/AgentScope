# AgentScope Instructions

This repo now has two clear execution modes:
- live runs against the Kubernetes environment
- replay runs against recorded benchmark episodes

## 1) Prerequisites

- Docker Desktop with Kubernetes enabled for live runs
- `kubectl`, `curl`, `python3`
- Python dependencies from `requirements.txt`
- Kubernetes context set to `docker-desktop` for local live use

Setup:

```bash
python3 -m pip install -r requirements.txt
kubectl cluster-info
kubectl config current-context
```

## 2) Start The Live System

From repo root:

```bash
./scripts/start_all.sh
```

Local URLs:
- Frontend: `http://localhost:8080`
- Jaeger: `http://localhost:16686`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

## 3) Validate Telemetry Before A Live Run

```bash
python3 ./scripts/validate_telemetry.py \
  --prom-url http://localhost:9090 \
  --jaeger-url http://localhost:16686 \
  --namespace default
```

## 4) Main Live Workflow

Run a live experiment with:

```bash
python3 ./scripts/run_experiment.py <experiment-yaml> [--skip-startup]
```

This orchestrates:
1. optional startup/reset
2. traffic generation and baseline collection
3. fault injection
4. detector monitoring
5. agent execution
6. artifact capture under `experiment_runs/...`

For evidence-only collection:

```bash
python3 ./scripts/run_evidence_probe.py <experiment-yaml> [--skip-startup]
```

## 5) Main Replay Workflow

Run the ReAct benchmark agent against a recorded episode:

```bash
python3 ./scripts/run_benchmark_agent.py \
  --agent-type react \
  --backend replay \
  --replay-dataset <episode-json> \
  --problem-description "Investigate the incident and propose a remediation." \
  --out-file replay_report.json
```

Current episode datasets live under:
- `datasets/episodes/`

## 6) Tooling Model

The primary agent uses typed tools through `AgentCloudInterface`:
- `get_k8s_state`
- `get_metrics`
- `get_logs`
- `get_traces`
- `get_dependency_traces`
- safe action tools such as `rollout_undo`, `restart_pod`, `patch_resources`, and `wait_and_monitor`

## 7) Current Agent Entry Point

Use the benchmark runner for both live and replay execution:

```bash
python3 ./scripts/run_benchmark_agent.py --agent-type react --backend live ...
```

The older standalone workflow agent entrypoint was removed during cleanup.

## 8) Useful Artifacts

Live runs write to:
- `experiment_runs/<timestamp>_<experiment-name>/`

Most useful files:
- `summary.json`
- `agent_report.json`
- `evaluation.json`
- `monitor.log`
- `telemetry_validation.log`
- `evidence_report.json` for evidence probes

Replay datasets live under:
- `datasets/episodes/<task_id>/`

## 9) Detection Standalone

Run a one-shot detector check with:

```bash
python3 ./scripts/detect_issue.py \
  --namespace default \
  --prom-url http://localhost:9090 \
  --target-deployment checkoutservice
```
