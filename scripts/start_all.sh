#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="default"
MANIFEST="vendor/microservices-demo/release/kubernetes-manifests.yaml"
ENABLE_TRAFFIC=0
ENABLE_BASELINE=0
TRAFFIC_DURATION=300
TRAFFIC_RPS=4
BASELINE_DURATION=300
BASELINE_INTERVAL=15
RUNTIME_DIR=".runtime"

usage() {
  cat <<USAGE
Start Online Boutique + observability stack with one command.

Usage:
  $(basename "$0") [options]

Options:
  -n <namespace>   Kubernetes namespace (default: default)
  -m <manifest>    App manifest path (default: vendor/microservices-demo/release/kubernetes-manifests.yaml)
  -t               Also start synthetic traffic in background
  -b               Also start baseline collector in background
  -h               Show help

Examples:
  ./scripts/start_all.sh
  ./scripts/start_all.sh -t -b
USAGE
}

while getopts ":n:m:tbh" opt; do
  case "$opt" in
    n) NAMESPACE="$OPTARG" ;;
    m) MANIFEST="$OPTARG" ;;
    t) ENABLE_TRAFFIC=1 ;;
    b) ENABLE_BASELINE=1 ;;
    h)
      usage
      exit 0
      ;;
    :)
      echo "Missing argument for -$OPTARG" >&2
      exit 1
      ;;
    \?)
      echo "Unknown option: -$OPTARG" >&2
      usage
      exit 1
      ;;
  esac
done

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required but not installed." >&2
  exit 1
fi

if [ ! -f "$MANIFEST" ]; then
  echo "Manifest not found: $MANIFEST" >&2
  exit 1
fi

mkdir -p "$RUNTIME_DIR"
TS_UTC=$(date -u +"%Y%m%dT%H%M%SZ")
RUN_DIR="$RUNTIME_DIR/start_all_$TS_UTC"
mkdir -p "$RUN_DIR"

echo "Run directory: $RUN_DIR"
echo "Namespace: $NAMESPACE"

echo "Applying app manifest: $MANIFEST"
kubectl apply -n "$NAMESPACE" -f "$MANIFEST"

echo "Waiting for frontend deployment..."
kubectl rollout status deployment/frontend -n "$NAMESPACE" --timeout=300s

echo "Setting up observability stack..."
./scripts/setup_observability.sh -n "$NAMESPACE"

start_pf() {
  local name="$1"
  local svc="$2"
  local map="$3"
  local log_file="$RUN_DIR/${name}.log"
  local pid_file="$RUN_DIR/${name}.pid"

  if [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" >/dev/null 2>&1; then
    echo "Port-forward already running for $name (pid $(cat "$pid_file"))"
    return
  fi

  kubectl port-forward -n "$NAMESPACE" "svc/$svc" "$map" >"$log_file" 2>&1 &
  echo $! >"$pid_file"
  sleep 1

  if kill -0 "$(cat "$pid_file")" >/dev/null 2>&1; then
    echo "Started port-forward $name -> $map (pid $(cat "$pid_file"))"
  else
    echo "Failed to start port-forward for $name. Check $log_file" >&2
  fi
}

echo "Starting port-forwards..."
start_pf frontend frontend "8080:80"
start_pf jaeger jaeger "16686:16686"
start_pf prometheus prometheus "9090:9090"
start_pf grafana grafana "3000:3000"

if [ "$ENABLE_TRAFFIC" -eq 1 ]; then
  echo "Starting synthetic traffic in background..."
  ./scripts/generate_traffic.sh -u http://localhost:8080 -d "$TRAFFIC_DURATION" -r "$TRAFFIC_RPS" >"$RUN_DIR/traffic.log" 2>&1 &
  echo $! >"$RUN_DIR/traffic.pid"
  echo "Traffic pid: $(cat "$RUN_DIR/traffic.pid")"
fi

if [ "$ENABLE_BASELINE" -eq 1 ]; then
  echo "Starting baseline collector in background..."
  ./scripts/collect_baseline.sh -n "$NAMESPACE" -i "$BASELINE_INTERVAL" -d "$BASELINE_DURATION" >"$RUN_DIR/baseline.log" 2>&1 &
  echo $! >"$RUN_DIR/baseline.pid"
  echo "Baseline pid: $(cat "$RUN_DIR/baseline.pid")"
fi

cat <<DONE

Everything is up.

URLs:
- Frontend:   http://localhost:8080
- Jaeger:     http://localhost:16686
- Prometheus: http://localhost:9090
- Grafana:    http://localhost:3000 (admin/admin)

Runtime files:
- Logs/PIDs: $RUN_DIR

To stop port-forwards quickly:
  kill \
    \\$(cat $RUN_DIR/frontend.pid) \
    \\$(cat $RUN_DIR/jaeger.pid) \
    \\$(cat $RUN_DIR/prometheus.pid) \
    \\$(cat $RUN_DIR/grafana.pid)
DONE
