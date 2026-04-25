# Observability Setup

This README is only for the local live environment. It is not required for replay-only benchmark reproduction.

## What The Live Stack Uses

- Online Boutique
- OpenTelemetry Collector
- Jaeger
- Prometheus
- Grafana
- kube-state-metrics

## Start The App

```bash
kubectl apply -f vendor/microservices-demo/release/kubernetes-manifests.yaml
```

## Install The Observability Stack

```bash
./scripts/setup_observability.sh -n default
```

This also patches Online Boutique deployments with tracing/metrics environment variables when those deployments are present.

## Open The UIs

```bash
kubectl port-forward -n default svc/jaeger 16686:16686
kubectl port-forward -n default svc/prometheus 9090:9090
kubectl port-forward -n default svc/grafana 3000:3000
kubectl port-forward -n default svc/frontend-external 8080:80
```

- Jaeger: <http://localhost:16686>
- Prometheus: <http://localhost:9090>
- Grafana: <http://localhost:3000>
- Frontend: <http://localhost:8080>

## Quick Validation

```bash
python3 scripts/validate_telemetry.py \
  --prom-url http://localhost:9090 \
  --jaeger-url http://localhost:16686 \
  --namespace default
```

## Traffic

```bash
./scripts/generate_traffic.sh -u http://localhost:8080 -d 120 -r 4
```

## Teardown

```bash
./scripts/teardown_observability.sh -n default
```
