# AgentScope Instructions

This file is the end-to-end runbook for the current AgentScope system.

## 1) Prerequisites

- Docker Desktop with Kubernetes enabled
- `kubectl`, `curl`, `python3`
- Kubernetes context set to `docker-desktop`

Check:

```bash
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
./scripts/generate_traffic.sh -u http://localhost:8080 -d 300 -r 1
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
./scripts/failure_inject.sh apply latency_spike -n default -l 5s -d 180
./scripts/failure_inject.sh apply cpu_pressure -n default -d 180
```

## 8) Minimal Agent Workflow (Rule-Based)

This is the current basic rule-based detect -> diagnose -> act -> verify loop.

Dry run (no action executed):

```bash
./scripts/agent_minimal.py --dry-run --namespace default --prom-url http://localhost:9090 --target-deployment cartservice
```

Real run (executes rollout restart if incident detected):

```bash
./scripts/agent_minimal.py --namespace default --prom-url http://localhost:9090 --target-deployment cartservice
```

Output report:
- `agent_runs/<timestamp>/incident_report.json`

## 9) Full Experiment Sequence (Suggested)

1. Start stack
```bash
./scripts/start_all.sh
```
2. Run baseline traffic
```bash
./scripts/generate_traffic.sh -u http://localhost:8080 -d 300 -r 1
```
3. Capture baseline screenshots (Prometheus/Grafana/Jaeger)
4. Inject one failure (for example service outage)
```bash
./scripts/service_outage.sh apply -n default -s cartservice -d 120
```
5. Run agent
```bash
./scripts/agent_minimal.py --namespace default --prom-url http://localhost:9090 --target-deployment cartservice
```
6. Capture during-failure and post-recovery screenshots + JSON report

## 10) Stop Everything

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

## 11) Authors

- Aarnav Sawant
- Sri Vamsi Putti
