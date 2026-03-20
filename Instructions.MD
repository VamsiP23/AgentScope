# AgentScope Instructions

This file is the end-to-end runbook for the current AgentScope system.

## 1) Prerequisites

- Docker Desktop with Kubernetes enabled
- `kubectl`, `curl`, `python3`
- Python dependencies from `requirements.txt`
- Kubernetes context set to `docker-desktop`

Check:

```bash
python3 -m pip install -r requirements.txt
kubectl cluster-info
kubectl config current-context
```

## 2) One-Command Startup

From repo root:

```bash
./scripts/start_all.sh
```

What this brings up:
- Online Boutique microservices
- OpenTelemetry Collector
- Jaeger
- Prometheus
- Grafana
- Local stability profile (cartservice hardening, loadgenerator disabled by default)

If needed, kill stale local forwards first:

```bash
pkill -f "kubectl port-forward"
```

## 3) UI URLs

- Frontend: http://localhost:8080
- Jaeger: http://localhost:16686
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (`admin` / `admin`)

If any URL does not load, restart the matching port-forward:

```bash
kubectl port-forward -n default svc/frontend 8080:80
kubectl port-forward -n default svc/jaeger 16686:16686
kubectl port-forward -n default svc/prometheus 9090:9090
kubectl port-forward -n default svc/grafana 3000:3000
```

## 4) Generate Baseline Traffic

```bash
./scripts/generate_traffic.sh -u http://localhost:8080 -d 300 -r 1 -m full-flow
```

Output:
- `traffic_runs/<timestamp>/requests.csv`
- `traffic_runs/<timestamp>/summary.txt`

## 5) Collect Baseline Cluster Metrics

```bash
./scripts/collect_baseline.sh -n default -i 15 -d 300
```

Output:
- `baseline_runs/<timestamp>/summary.csv`
- snapshots/events/top outputs in same folder

## 6) Recommended Prometheus Queries

Use these in http://localhost:9090:

```promql
sum(rate(calls_total[1m])) by (service_name)
```

```promql
sum(rate(calls_total{status_code="STATUS_CODE_ERROR"}[1m])) by (service_name)
```

```promql
sum(rate(calls_total[1m]))
```

## 7) Failure Injection

Shared fault logic now lives in the Python package `faults/`. `./scripts/failure_inject.sh` remains the stable CLI wrapper.

### A) Single-service outage helper

```bash
./scripts/service_outage.sh apply -n default -s checkoutservice -d 120
```

Revert manually:

```bash
./scripts/service_outage.sh revert -n default -s checkoutservice
```

### B) Multi-scenario injector

```bash
./scripts/failure_inject.sh apply service_outage -n default -t checkoutservice -d 120
./scripts/failure_inject.sh apply dependency_outage -n default -d 120
./scripts/failure_inject.sh apply cpu_throttling -n default -t productcatalogservice --cpu-request 25m --cpu-limit 50m -d 180
./scripts/failure_inject.sh apply replica_reduction_under_load -n default -t checkoutservice -r 1 -d 120
```

## 8) Detection Layer

Use the detectors module to decide whether there is an issue before doing any diagnosis or remediation.

Run detection once:

```bash
./scripts/detect_issue.py --namespace default --prom-url http://localhost:9090 --target-deployment cartservice
```

What it checks:
- global error ratio
- top service-level error rate
- target deployment availability
- historical pod restart counts as supporting context

It prints a structured JSON report with:
- `incident_detected`
- `suspicious_services`
- per-detector findings and thresholds

## 8.5) LangGraph Agent

The agent is now organized around the `agent_graph/` package:

- [`agent_graph/README.md`](/Users/aarnavsawant/Documents/CS6365/AgentScope/agent_graph/README.md)
- [`agent_graph/state.py`](/Users/aarnavsawant/Documents/CS6365/AgentScope/agent_graph/state.py)
- [`agent_graph/workflow.py`](/Users/aarnavsawant/Documents/CS6365/AgentScope/agent_graph/workflow.py)
- [`agent_graph/nodes/detect.py`](/Users/aarnavsawant/Documents/CS6365/AgentScope/agent_graph/nodes/detect.py)
- [`agent_graph/nodes/hypothesize.py`](/Users/aarnavsawant/Documents/CS6365/AgentScope/agent_graph/nodes/hypothesize.py)
- [`agent_graph/nodes/research.py`](/Users/aarnavsawant/Documents/CS6365/AgentScope/agent_graph/nodes/research.py)
- [`agent_graph/nodes/act.py`](/Users/aarnavsawant/Documents/CS6365/AgentScope/agent_graph/nodes/act.py)
- [`agent_graph/nodes/verify.py`](/Users/aarnavsawant/Documents/CS6365/AgentScope/agent_graph/nodes/verify.py)
- [`agent_graph/knowledge/topology.py`](/Users/aarnavsawant/Documents/CS6365/AgentScope/agent_graph/knowledge/topology.py)

Run the LangGraph agent through the stable wrapper:

```bash
./scripts/run_agent.py \
  --namespace default \
  --prom-url http://localhost:9090 \
  --jaeger-url http://localhost:16686 \
  --target-deployment cartservice \
  --mode heuristic \
  --dry-run
```

This workflow does:
- detector -> incident context
- Online Boutique topology -> service role/dependency context
- LangGraph state machine:
  - detect
  - hypothesize
  - research
  - act
  - verify
- if verification fails, loop back to hypothesize until max iterations are exhausted

Optional LLM-backed hypothesis generation:

```bash
OPENAI_API_KEY=... ./scripts/run_agent.py \
  --namespace default \
  --prom-url http://localhost:9090 \
  --jaeger-url http://localhost:16686 \
  --target-deployment cartservice \
  --mode llm \
  --dry-run
```

## 9) YAML-Driven Experiments

The experiment runner can now do the full loop in one command:
- start the stack
- generate traffic
- start the monitor loop
- inject the fault
- capture before/during/after artifacts


Reproducible experiments now live under `experiments/`.

Run one experiment from a YAML file:

```bash
./scripts/run_experiment.sh experiments/service_outage_cartservice.yaml
```

If the stack is already running and you do not want to call `start_all.sh` again:

```bash
./scripts/run_experiment.sh experiments/service_outage_cartservice.yaml --skip-startup
```

Example experiment files:
- `experiments/service_outage_cartservice.yaml`
- `experiments/dependency_outage_redis_cart.yaml`
- `experiments/cpu_throttling_productcatalog.yaml`
- `experiments/replica_reduction_checkoutservice.yaml`

Each run writes artifacts under:
- `experiment_runs/<timestamp>_<experiment-name>/`

Artifacts include:
- copied experiment YAML
- startup/fault logs
- `agent.log`
- `agent_report.json`
- before/during/after Kubernetes snapshots
- `summary.json` with the full run timeline

## 10) Full Experiment Sequence (Suggested)

1. Start stack
```bash
./scripts/start_all.sh
```
2. Run baseline traffic
```bash
./scripts/generate_traffic.sh -u http://localhost:8080 -d 300 -r 1 -m full-flow
```
3. Capture baseline screenshots (Prometheus/Grafana/Jaeger)
4. Inject one failure (for example service outage)
```bash
./scripts/service_outage.sh apply -n default -s cartservice -d 120
```
5. Capture during-failure and post-recovery screenshots + run artifacts

## 11) Stop Everything

Stop background processes from latest start run:

```bash
./scripts/stop_all.sh
```

Remove observability stack:

```bash
./scripts/teardown_observability.sh -n default
```

Remove Online Boutique:

```bash
kubectl delete -f vendor/microservices-demo/release/kubernetes-manifests.yaml
```

## 12) Authors

- Aarnav Sawant
- Sri Vamsi Putti
