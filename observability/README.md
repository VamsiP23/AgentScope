# Observability Stack (Local Kubernetes)

This repo includes a local observability stack for Online Boutique:
- OpenTelemetry Collector (`opentelemetrycollector`)
- Jaeger (`jaeger`)
- Prometheus (`prometheus`)
- Grafana (`grafana`)

## 1) Deploy app (full Online Boutique)

```bash
kubectl apply -f vendor/microservices-demo/release/kubernetes-manifests.yaml
```

## 2) Deploy observability stack + patch service env vars

```bash
./scripts/setup_observability.sh -n default
```

The setup script patches these deployments (if present) with:
- `ENABLE_TRACING=1`
- `ENABLE_STATS=1`
- `COLLECTOR_SERVICE_ADDR=opentelemetrycollector:4317`

## 3) Open UIs

Run each in a separate terminal:

```bash
kubectl port-forward -n default svc/jaeger 16686:16686
kubectl port-forward -n default svc/prometheus 9090:9090
kubectl port-forward -n default svc/grafana 3000:3000
```

- Jaeger: http://localhost:16686
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (login `admin/admin`)

## 4) Generate traffic

```bash
./scripts/generate_traffic.sh -u http://localhost:8080 -d 300 -r 4
```

This will produce traces and metrics while traffic runs.

## 5) Verify telemetry flow quickly

```bash
kubectl logs deploy/opentelemetrycollector -n default --tail=100
kubectl get pods -n default | grep -E "opentelemetrycollector|jaeger|prometheus|grafana"
```

## 6) Teardown

```bash
./scripts/teardown_observability.sh -n default
```
