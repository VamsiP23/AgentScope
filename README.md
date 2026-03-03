# AgentScope

AgentScope uses Google's Online Boutique as a distributed microservices system for failure monitoring, observability baselining, and agent-driven recovery experiments.

## What This Repo Gives You

- Baseline metric collector for Kubernetes health/resource snapshots
- Synthetic traffic generator for repeatable load
- Local observability stack on Kubernetes:
  - OpenTelemetry Collector
  - Jaeger
  - Prometheus
  - Grafana
- Setup scripts to wire Online Boutique services to OTel automatically

## Prerequisites

- Docker Desktop
- Kubernetes enabled in Docker Desktop
- `kubectl`
- `curl`

Verify cluster access:

```bash
kubectl cluster-info
kubectl config current-context
```

Expected context on Docker Desktop: `docker-desktop`

## Clone

```bash
git clone --recursive https://github.com/VamsiP23/AgentScope.git
cd AgentScope
```

## Deploy Online Boutique

Use the full upstream manifest (recommended for observability work):

```bash
kubectl apply -f vendor/microservices-demo/release/kubernetes-manifests.yaml
kubectl get pods -n default
```

Note: `saved_manifests/onlineboutique.yaml` in this repo is a reduced manifest and may not include all services.

## Bring Up Observability Stack

Deploy OTel Collector + Jaeger + Prometheus + Grafana and patch service env vars:

```bash
./scripts/setup_observability.sh -n default
```

This patches Online Boutique deployments (if present) with:

- `ENABLE_TRACING=1`
- `ENABLE_STATS=1`
- `COLLECTOR_SERVICE_ADDR=opentelemetrycollector:4317`
- `OTEL_SERVICE_NAME=<deployment>`
- `OTEL_RESOURCE_ATTRIBUTES=service.name=<deployment>,deployment.environment=local`

## Open UIs (3 Terminals)

```bash
kubectl port-forward -n default svc/jaeger 16686:16686
kubectl port-forward -n default svc/prometheus 9090:9090
kubectl port-forward -n default svc/grafana 3000:3000
```

- Jaeger: http://localhost:16686
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
  - Login: `admin` / `admin`

Frontend:

```bash
kubectl port-forward -n default svc/frontend 8080:80
```

- App: http://localhost:8080

## Generate Load

```bash
./scripts/generate_traffic.sh -u http://localhost:8080 -d 300 -r 4
```

Outputs:

- `traffic_runs/<timestamp>/requests.csv`
- `traffic_runs/<timestamp>/summary.txt`

## Collect Baseline Kubernetes Metrics

```bash
./scripts/collect_baseline.sh -n default -i 15 -d 300
```

Outputs:

- `baseline_runs/<timestamp>/summary.csv`
- pod snapshots, events, `kubectl top` outputs

If metrics-server is missing, top files will contain a warning but collection continues.

## Validate Jaeger

In Jaeger Search:

1. Set `Service = frontend`
2. Set `Lookback = Last 15 min`
3. Optionally set `Min Duration = 10ms` to reduce health-check noise
4. Click `Find Traces`

Expected:

- Service names like `frontend`, `checkoutservice`, `currencyservice`, etc.
- Multi-span traces for real user flows

If you mostly see `grpc.health.v1.Health/Check`, that is probe traffic. Keep synthetic traffic running and query `frontend`.

## Validate Prometheus

Important: ensure query time is set to **Now** (not a fixed old timestamp).

Try these queries:

```promql
up{job="otel-collector"}
```

```promql
calls_total
```

```promql
sum(rate(calls_total[1m])) by (service_name)
```

```promql
histogram_quantile(0.95, sum(rate(duration_bucket[1m])) by (le, service_name))
```

## Basic Grafana Workflow

1. Open Grafana: http://localhost:3000
2. `Connections -> Data sources -> Prometheus -> Save & test`
3. `Dashboards -> New -> Add visualization`
4. Paste queries like:

```promql
sum(rate(calls_total[1m])) by (service_name)
```

```promql
sum(rate(calls_total{status_code="STATUS_CODE_ERROR"}[1m])) by (service_name)
```

```promql
histogram_quantile(0.95, sum(rate(duration_bucket[1m])) by (le, service_name))
```

## Troubleshooting

### `kubectl get pods` shows nothing

- Check cluster/context:

```bash
kubectl config current-context
kubectl get ns
```

- Re-apply manifest to current context:

```bash
kubectl apply -f vendor/microservices-demo/release/kubernetes-manifests.yaml
```

### Traffic script exits too quickly or outputs zero requests

- Verify frontend is reachable:

```bash
curl -I http://localhost:8080
```

- Ensure frontend port-forward is running.

### Jaeger shows `unknown_service:*`

- Re-run setup to patch `OTEL_SERVICE_NAME`:

```bash
./scripts/setup_observability.sh -n default
```

### Prometheus shows empty results

- Make sure query time is set to `Now`
- Keep traffic running while querying
- Confirm scrape target:

```promql
up{job="otel-collector"}
```

### Add-to-cart issues

```bash
kubectl rollout restart deploy/redis-cart -n default
kubectl rollout restart deploy/cartservice -n default
```

## Teardown

Remove observability stack:

```bash
./scripts/teardown_observability.sh -n default
```

Remove Online Boutique:

```bash
kubectl delete -f vendor/microservices-demo/release/kubernetes-manifests.yaml
```

## Failure Injection (for Agent Evaluation)

Run deterministic failure scenarios for outage, dependency failure, latency, and CPU pressure:

```bash
./scripts/failure_inject.sh apply service_outage -n default -t checkoutservice -d 120
./scripts/failure_inject.sh apply dependency_outage -n default -d 120
./scripts/failure_inject.sh apply latency_spike -n default -l 5s -d 180
./scripts/failure_inject.sh apply cpu_pressure -n default -d 180
```

## Additional Docs

- Local observability details: `observability/README.md`
- Failure scenarios + evaluation rubric: `failure_scenarios/README.md`

## Authors

- Aarnav Sawant
- Sri Vamsi Putti
