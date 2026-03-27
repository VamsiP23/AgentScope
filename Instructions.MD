# AgentScope Instructions

This runbook is focused on the main workflow of the repository: running repeatable experiments, observing the detector and agent, and inspecting the artifacts afterward.

## 1) Prerequisites

- Docker Desktop with Kubernetes enabled
- `kubectl`, `curl`, `python3`
- Python dependencies from `requirements.txt`
- Kubernetes context set to `docker-desktop`

Setup:

```bash
python3 -m pip install -r requirements.txt
kubectl cluster-info
kubectl config current-context
```

## 2) Start The System

From repo root:

```bash
./scripts/start_all.sh
```

This starts:
- Online Boutique microservices
- OpenTelemetry Collector
- Jaeger
- Prometheus
- Grafana

Local URLs:
- Frontend: http://localhost:8080
- Jaeger: http://localhost:16686
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

If a UI does not load, restart the matching port-forward:

```bash
kubectl port-forward -n default svc/frontend 8080:80
kubectl port-forward -n default svc/jaeger 16686:16686
kubectl port-forward -n default svc/prometheus 9090:9090
kubectl port-forward -n default svc/grafana 3000:3000
```

## 3) Main Workflow: Run An Experiment

The primary entrypoint is:

```bash
./scripts/run_experiment.sh <experiment-yaml> [--skip-startup]
```

Recommended first run:

```bash
./scripts/run_experiment.sh <experiment-yaml> --skip-startup
```

Use `--skip-startup` when the stack is already running.

## 4) What An Experiment Does

`run_experiment.sh` orchestrates the full workflow:

1. captures a before snapshot
2. starts traffic generation
3. starts baseline collection
4. starts the detector/monitor loop
5. waits for the pre-fault delay
6. injects the configured fault, if the experiment defines one
7. captures a during snapshot
8. waits for detector confirmation
9. runs the LangGraph agent
10. waits through the post-fault period
11. reverts the fault only if needed
12. captures an after snapshot
13. writes all artifacts to `experiment_runs/...`

## 5) Available Experiment YAMLs

The legacy fault-backed experiment YAMLs were removed with the old `faults/` package.

Current state:
- use `experiments/README.md` as the source of truth
- do not reference `fault.scenario` until the Chaos Mesh backend is added
- no prebuilt faulted experiment YAMLs are checked in right now

## 6) Example Runs

No prebuilt faulted experiment examples are checked in right now because the old fault framework has been removed and the Chaos Mesh replacement has not been wired into the runner yet.

## 7) What To Watch During A Run

The experiment runner prints live phase updates.

Important phases:
- `phase=traffic`
- `phase=baseline`
- `phase=monitor`
- `phase=fault_apply` if a fault is configured
- `phase=agent_wait`
- `phase=agent`
- `phase=fault_revert` if a fault is configured

Important streamed outputs:

### Detector output
Prefixed with:

```text
[monitor]
```

This tells you:
- when the incident is first detected
- which detector signal triggered
- how severity evolves during the fault

### Agent output
Prefixed with:

```text
[agent]
```

This tells you:
- the current LangGraph state
- generated hypotheses
- supported hypothesis
- selected action
- verification result

## 8) How To Interpret A Good Run

A healthy run should show:

1. detector starts healthy
2. traffic and baseline collection begin
3. if a fault is configured, the runner applies it and the detector reacts
4. the agent starts after detector confirmation
5. the agent gathers trace, metric, and Kubernetes evidence
6. the agent either selects an action or reports that recovery is already progressing
7. verification records whether the root cause was mitigated and whether user-facing recovery followed

## 9) Artifacts After A Run

Each experiment writes to:

- `experiment_runs/<timestamp>_<experiment-name>/`

Key files:
- `experiment.yaml`
- `traffic.log`
- `baseline.log`
- `monitor.log`
- `agent.log`
- `agent_report.json`
- `summary.json`
- `before_*`
- `during_*`
- `after_*`

Most useful artifacts:

### `agent_report.json`
Contains:
- incident context
- hypotheses
- evidence bundle
- attempted actions
- verification result

### `summary.json`
Contains:
- experiment phases
- return codes
- timing
- artifact references

### `monitor.log`
Contains:
- detector state changes
- severity evolution over time

## 10) How To Inspect Jaeger During Experiments

Open:
- http://localhost:16686

Best practice:
- start from the symptom service, usually `frontend`
- inspect failing traces during the fault window
- identify the failing downstream hop

For example, during a `cartservice` outage:
- `frontend` traces may show downstream calls to `cartservice` failing

That is often more useful than searching for traces starting from the failed backend itself.

## 11) Running The Agent Standalone

You can run the LangGraph agent without the full experiment runner:

```bash
./scripts/run_agent.py \
  --namespace default \
  --prom-url http://localhost:9090 \
  --jaeger-url http://localhost:16686 \
  --target-deployment cartservice \
  --mode llm \
  --dry-run
```

Use this for debugging the agent in isolation.

## 12) Running Detection Standalone

Run a one-shot detector check:

```bash
./scripts/detect_issue.py \
  --namespace default \
  --prom-url http://localhost:9090 \
  --target-deployment cartservice
```

This prints a structured JSON report with:
- `incident_detected`
- `suspicious_services`
- per-signal findings

## 13) Fault Injection Status

The legacy custom fault framework has been removed.

Current state:
- `faults/` has been deleted
- `scripts/failure_inject.sh` has been removed
- old scale/patch fault experiment YAMLs have been removed

Until the Chaos Mesh backend is wired into the repo, do not reference `fault.scenario` in experiment YAMLs.

## 14) Baseline And Traffic Utilities

Generate traffic only:

```bash
./scripts/generate_traffic.sh -u http://localhost:8080 -d 300 -r 1 -m full-flow
```

Collect baseline only:

```bash
./scripts/collect_baseline.sh -n default -i 15 -d 300
```

These write to:
- `traffic_runs/...`
- `baseline_runs/...`

## 15) Prometheus Queries

Useful queries:

```promql
sum(rate(calls_total[1m])) by (service_name)
```

```promql
sum(rate(calls_total{status_code="STATUS_CODE_ERROR"}[1m])) by (service_name)
```

```promql
sum(rate(calls_total[1m]))
```

## 16) Shutdown

Stop background processes from the latest startup:

```bash
./scripts/stop_all.sh
```

Remove the observability stack:

```bash
./scripts/teardown_observability.sh -n default
```
