# Observability Setup

This README is only for the local live environment. It is not required for replay-only benchmark reproduction.

## Live Demo Prerequisites

Before you do any Kubernetes setup, make sure you already have:

- a Python virtual environment created for this repo
- dependencies installed with `pip install -r requirements.txt`
- `ANTHROPIC_API_KEY` exported in the shell you will use for the demo

For example:

```bash
cd <repo-root>
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key_here
```

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

After applying the app, wait until the core deployments are ready:

```bash
kubectl get pods -n default
kubectl get deploy -n default
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

You should do this validation before attempting the live demo. If this step fails, the replay benchmark will still work, but the live demo likely will not.

## Traffic

```bash
./scripts/generate_traffic.sh -u http://localhost:8080 -d 120 -r 4
```

## Run The Live Demo

Once the app, observability stack, and API key are ready:

```bash
zsh -lic 'cd <repo-root> && ./scripts/run_live_fix_demo.sh'
```

Use this `zsh -lic` form if your API key lives in `~/.zshrc` or `~/.zprofile`.

If the demo fails early:

- `ANTHROPIC_API_KEY is not set`: export the key in the current shell
- `Unable to connect to the server: net/http: TLS handshake timeout`: your Kubernetes API server is not responding yet
- telemetry validation errors: fix the Prometheus/Jaeger setup before retrying

## Teardown

```bash
./scripts/teardown_observability.sh -n default
```
