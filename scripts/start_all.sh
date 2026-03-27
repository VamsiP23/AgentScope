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
PF_FAILED=0
DISABLE_BUILTIN_LOADGEN=1
STABLE_LOCAL_MODE=1
KUBE_CONTEXT=""
CHAOS_MESH_NAMESPACE="chaos-mesh"
CHAOS_MESH_RELEASE="chaos-mesh"
CHAOS_MESH_CHART="chaos-mesh/chaos-mesh"
CHAOS_DAEMON_RUNTIME="${CHAOS_DAEMON_RUNTIME:-docker}"
CHAOS_DAEMON_SOCKET_PATH="${CHAOS_DAEMON_SOCKET_PATH:-/var/run/docker.sock}"
KEY_MULTI_REPLICA_DEPLOYMENTS=(
  frontend:2
  cartservice:2
  checkoutservice:2
  productcatalogservice:2
)

usage() {
  cat <<USAGE
Start Online Boutique + observability stack with one command.

Usage:
  $(basename "$0") [options]

Options:
  -n <namespace>   Kubernetes namespace (default: default)
  -m <manifest>    App manifest path (default: vendor/microservices-demo/release/kubernetes-manifests.yaml)
  -c <context>     Use this existing kubectl context (example: docker-desktop)
  -g               Keep built-in Online Boutique loadgenerator enabled
  -s               Skip stable local hardening (cartservice probe tuning)
  -t               Also start synthetic traffic in background
  -b               Also start baseline collector in background
  -h               Show help

Examples:
  ./scripts/start_all.sh
  ./scripts/start_all.sh -c docker-desktop
  ./scripts/start_all.sh -t -b
USAGE
}

while getopts ":n:m:c:gstbh" opt; do
  case "$opt" in
    n) NAMESPACE="$OPTARG" ;;
    m) MANIFEST="$OPTARG" ;;
    c) KUBE_CONTEXT="$OPTARG" ;;
    g) DISABLE_BUILTIN_LOADGEN=0 ;;
    s) STABLE_LOCAL_MODE=0 ;;
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

ensure_brew_package() {
  local tool="$1"

  if command -v "$tool" >/dev/null 2>&1; then
    return
  fi

  if ! command -v brew >/dev/null 2>&1; then
    echo "$tool is required but not installed, and Homebrew is not available for automatic installation." >&2
    exit 1
  fi

  echo "Installing $tool with Homebrew..."
  brew install "$tool"
}

ensure_helm_binary() {
  ensure_brew_package helm
}

ensure_current_cluster() {
  local context_name

  if [ -n "$KUBE_CONTEXT" ]; then
    context_name="$KUBE_CONTEXT"
  else
    context_name=$(kubectl config current-context 2>/dev/null || true)
  fi

  if [ -z "$context_name" ]; then
    echo "No kubectl context is configured. Use -c <context> or configure kubectl first." >&2
    exit 1
  fi

  echo "Using existing kubectl context: $context_name"
  kubectl config use-context "$context_name" >/dev/null

  echo "Waiting for nodes in current cluster to become Ready..."
  kubectl wait --for=condition=Ready nodes --all --timeout=180s >/dev/null
  kubectl get nodes
}

ensure_chaos_mesh() {
  ensure_helm_binary

  if ! kubectl get namespace "$CHAOS_MESH_NAMESPACE" >/dev/null 2>&1; then
    echo "Creating namespace: $CHAOS_MESH_NAMESPACE"
    kubectl create namespace "$CHAOS_MESH_NAMESPACE" >/dev/null
  fi

  echo "Installing or upgrading Chaos Mesh..."
  helm repo add chaos-mesh https://charts.chaos-mesh.org >/dev/null 2>&1 || true
  helm repo update >/dev/null
  helm upgrade --install "$CHAOS_MESH_RELEASE" "$CHAOS_MESH_CHART" \
    -n "$CHAOS_MESH_NAMESPACE" \
    --set chaosDaemon.runtime="$CHAOS_DAEMON_RUNTIME" \
    --set chaosDaemon.socketPath="$CHAOS_DAEMON_SOCKET_PATH" >/dev/null

  echo "Waiting for Chaos Mesh components..."
  kubectl rollout status deployment/chaos-controller-manager -n "$CHAOS_MESH_NAMESPACE" --timeout=300s >/dev/null
  if kubectl get daemonset/chaos-daemon -n "$CHAOS_MESH_NAMESPACE" >/dev/null 2>&1; then
    kubectl rollout status daemonset/chaos-daemon -n "$CHAOS_MESH_NAMESPACE" --timeout=300s >/dev/null
  fi
  if kubectl get deployment/chaos-dashboard -n "$CHAOS_MESH_NAMESPACE" >/dev/null 2>&1; then
    kubectl rollout status deployment/chaos-dashboard -n "$CHAOS_MESH_NAMESPACE" --timeout=300s >/dev/null
  fi
}

ensure_namespace() {
  if kubectl get namespace "$NAMESPACE" >/dev/null 2>&1; then
    return
  fi

  echo "Creating namespace: $NAMESPACE"
  kubectl create namespace "$NAMESPACE" >/dev/null
}

scale_key_deployments() {
  local entry deploy replicas

  echo "Scaling key services for resilience..."
  for entry in "${KEY_MULTI_REPLICA_DEPLOYMENTS[@]}"; do
    deploy="${entry%%:*}"
    replicas="${entry##*:}"

    if kubectl get deployment "$deploy" -n "$NAMESPACE" >/dev/null 2>&1; then
      kubectl scale deployment/"$deploy" -n "$NAMESPACE" --replicas="$replicas" >/dev/null
      kubectl rollout status deployment/"$deploy" -n "$NAMESPACE" --timeout=300s >/dev/null
      echo "  deployment/$deploy scaled to $replicas"
    else
      echo "  deployment/$deploy not found, skipping"
    fi
  done
}

if [ ! -f "$MANIFEST" ]; then
  echo "Manifest not found: $MANIFEST" >&2
  exit 1
fi

ensure_current_cluster

ensure_chaos_mesh

ensure_namespace

mkdir -p "$RUNTIME_DIR"
TS_UTC=$(date -u +"%Y%m%dT%H%M%SZ")
RUN_DIR="$RUNTIME_DIR/start_all_$TS_UTC"
mkdir -p "$RUN_DIR"

echo "Run directory: $RUN_DIR"
echo "Namespace: $NAMESPACE"

echo "Applying app manifest: $MANIFEST"
kubectl apply -n "$NAMESPACE" -f "$MANIFEST"

scale_key_deployments

if [ "$DISABLE_BUILTIN_LOADGEN" -eq 1 ]; then
  if kubectl get deployment/loadgenerator -n "$NAMESPACE" >/dev/null 2>&1; then
    echo "Scaling built-in loadgenerator to 0 for local stability..."
    kubectl scale deployment/loadgenerator -n "$NAMESPACE" --replicas=0 >/dev/null
  fi
fi

if [ "$STABLE_LOCAL_MODE" -eq 1 ]; then
  if kubectl get deployment/cartservice -n "$NAMESPACE" >/dev/null 2>&1; then
    echo "Applying stable local probe settings for cartservice..."
    kubectl patch deployment cartservice -n "$NAMESPACE" --type='json' -p='[
      {"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/initialDelaySeconds","value":45},
      {"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/timeoutSeconds","value":10},
      {"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/failureThreshold","value":20},
      {"op":"remove","path":"/spec/template/spec/containers/0/livenessProbe"},
      {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/cpu","value":"300m"},
      {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"128Mi"},
      {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/cpu","value":"1000m"},
      {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"512Mi"}
    ]' >/dev/null
  fi

  if kubectl get deployment/currencyservice -n "$NAMESPACE" >/dev/null 2>&1; then
    echo "Applying stable local probe settings for currencyservice..."
    kubectl patch deployment currencyservice -n "$NAMESPACE" --type='json' -p='[
      {"op":"add","path":"/spec/template/spec/containers/0/readinessProbe/initialDelaySeconds","value":20},
      {"op":"add","path":"/spec/template/spec/containers/0/readinessProbe/timeoutSeconds","value":5},
      {"op":"add","path":"/spec/template/spec/containers/0/readinessProbe/failureThreshold","value":10},
      {"op":"add","path":"/spec/template/spec/containers/0/livenessProbe/initialDelaySeconds","value":30},
      {"op":"add","path":"/spec/template/spec/containers/0/livenessProbe/timeoutSeconds","value":5},
      {"op":"add","path":"/spec/template/spec/containers/0/livenessProbe/failureThreshold","value":10},
      {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/cpu","value":"200m"},
      {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"128Mi"},
      {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/cpu","value":"500m"},
      {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"256Mi"}
    ]' >/dev/null
  fi
fi

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
    PF_FAILED=1
  fi
}

wait_core_deployments() {
  local deploy
  local core=(
    frontend
    cartservice
    checkoutservice
    currencyservice
    productcatalogservice
    recommendationservice
    shippingservice
    paymentservice
    emailservice
    adservice
    redis-cart
  )

  echo "Waiting for core Online Boutique deployments to be available..."
  for deploy in "${core[@]}"; do
    if kubectl get deployment "$deploy" -n "$NAMESPACE" >/dev/null 2>&1; then
      kubectl rollout status deployment/"$deploy" -n "$NAMESPACE" --timeout=300s >/dev/null
      echo "  deployment/$deploy ready"
    else
      echo "  deployment/$deploy not found, skipping"
    fi
  done
}

echo "Starting port-forwards..."
start_pf frontend frontend "8080:80"
start_pf jaeger jaeger "16686:16686"
start_pf prometheus prometheus "9090:9090"
start_pf grafana grafana "3000:3000"

wait_core_deployments

if [ "$PF_FAILED" -ne 0 ]; then
  echo ""
  echo "One or more port-forwards failed. Check logs in: $RUN_DIR" >&2
  echo "Most common cause: local ports already in use (8080, 16686, 9090, 3000)." >&2
  echo "Fix: pkill -f \"kubectl port-forward\" and rerun ./scripts/start_all.sh" >&2
  exit 1
fi

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
