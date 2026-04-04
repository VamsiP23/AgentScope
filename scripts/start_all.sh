#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="default"
MANIFEST="vendor/microservices-demo/release/kubernetes-manifests.yaml"
ENABLE_TRAFFIC=0
ENABLE_BASELINE=0
TRAFFIC_DURATION=300
TRAFFIC_RPS=4
TRAFFIC_MODE="${TRAFFIC_MODE:-realistic}"
BASELINE_DURATION=300
BASELINE_INTERVAL=15
RUNTIME_DIR=".runtime"
PORT_FORWARD_DIR="$RUNTIME_DIR/port_forwards"
PF_FAILED=0
DISABLE_BUILTIN_LOADGEN=1
STABLE_LOCAL_MODE=1
KUBE_CONTEXT=""
CHAOS_MESH_NAMESPACE="chaos-mesh"
CHAOS_MESH_RELEASE="chaos-mesh"
CHAOS_MESH_CHART="chaos-mesh/chaos-mesh"
CHAOS_DAEMON_RUNTIME="${CHAOS_DAEMON_RUNTIME:-docker}"
CHAOS_DAEMON_SOCKET_PATH="${CHAOS_DAEMON_SOCKET_PATH:-/var/run/docker.sock}"
OBSERVABILITY_DEPLOYMENTS=(
  opentelemetrycollector
  kube-state-metrics
  jaeger
  prometheus
  grafana
)
KEY_MULTI_REPLICA_DEPLOYMENTS=(
  frontend:2
  cartservice:2
  checkoutservice:2
  productcatalogservice:2
)
CORE_DEPLOYMENTS=(
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
  opentelemetrycollector
  kube-state-metrics
  jaeger
  prometheus
  grafana
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
  -s               Skip stable local hardening (probe/resource tuning)
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

ensure_brew_package curl

ensure_helm_binary() {
  ensure_brew_package helm
}

retry_cmd() {
  local attempts="$1"
  local sleep_seconds="$2"
  shift 2
  local try

  for try in $(seq 1 "$attempts"); do
    if "$@"; then
      return 0
    fi
    if [ "$try" -lt "$attempts" ]; then
      sleep "$sleep_seconds"
    fi
  done

  return 1
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
  retry_cmd 5 3 kubectl config use-context "$context_name" >/dev/null

  echo "Waiting for nodes in current cluster to become Ready..."
  retry_cmd 5 5 kubectl wait --for=condition=Ready nodes --all --timeout=180s >/dev/null
  retry_cmd 5 3 kubectl get nodes
}

deployment_is_available() {
  local namespace="$1"
  local deploy="$2"
  local desired available

  if ! kubectl get deployment "$deploy" -n "$namespace" >/dev/null 2>&1; then
    return 1
  fi

  desired=$(kubectl get deployment "$deploy" -n "$namespace" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo 0)
  available=$(kubectl get deployment "$deploy" -n "$namespace" -o jsonpath='{.status.availableReplicas}' 2>/dev/null || echo 0)
  desired=${desired:-0}
  available=${available:-0}

  [ "$desired" -eq 0 ] || [ "$available" -ge "$desired" ]
}

observability_stack_healthy() {
  local deploy
  for deploy in "${OBSERVABILITY_DEPLOYMENTS[@]}"; do
    if ! deployment_is_available "$NAMESPACE" "$deploy"; then
      return 1
    fi
  done
  return 0
}

chaos_mesh_healthy() {
  local controller_ready ds_desired ds_ready

  if ! kubectl get namespace "$CHAOS_MESH_NAMESPACE" >/dev/null 2>&1; then
    return 1
  fi

  if ! kubectl get deployment/chaos-controller-manager -n "$CHAOS_MESH_NAMESPACE" >/dev/null 2>&1; then
    return 1
  fi

  controller_ready=$(kubectl get deployment chaos-controller-manager -n "$CHAOS_MESH_NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo 0)
  controller_ready=${controller_ready:-0}
  if [ "$controller_ready" -lt 1 ]; then
    return 1
  fi

  if kubectl get daemonset/chaos-daemon -n "$CHAOS_MESH_NAMESPACE" >/dev/null 2>&1; then
    ds_desired=$(kubectl get daemonset chaos-daemon -n "$CHAOS_MESH_NAMESPACE" -o jsonpath='{.status.desiredNumberScheduled}' 2>/dev/null || echo 0)
    ds_ready=$(kubectl get daemonset chaos-daemon -n "$CHAOS_MESH_NAMESPACE" -o jsonpath='{.status.numberReady}' 2>/dev/null || echo 0)
    ds_desired=${ds_desired:-0}
    ds_ready=${ds_ready:-0}
    if [ "$ds_desired" -gt 0 ] && [ "$ds_ready" -lt "$ds_desired" ]; then
      return 1
    fi
  fi

  if kubectl get deployment/chaos-dashboard -n "$CHAOS_MESH_NAMESPACE" >/dev/null 2>&1; then
    if ! deployment_is_available "$CHAOS_MESH_NAMESPACE" "chaos-dashboard"; then
      return 1
    fi
  fi

  return 0
}

ensure_chaos_mesh() {
  if chaos_mesh_healthy; then
    echo "Reusing existing healthy Chaos Mesh installation."
    return
  fi

  ensure_helm_binary

  if ! kubectl get namespace "$CHAOS_MESH_NAMESPACE" >/dev/null 2>&1; then
    echo "Creating namespace: $CHAOS_MESH_NAMESPACE"
    kubectl create namespace "$CHAOS_MESH_NAMESPACE" >/dev/null
  fi

  echo "Chaos Mesh is missing or unhealthy; repairing installation..."
  helm repo add chaos-mesh https://charts.chaos-mesh.org >/dev/null 2>&1 || true
  retry_cmd 3 5 helm repo update >/dev/null
  retry_cmd 3 5 helm upgrade --install "$CHAOS_MESH_RELEASE" "$CHAOS_MESH_CHART" \
    -n "$CHAOS_MESH_NAMESPACE" \
    --set chaosDaemon.runtime="$CHAOS_DAEMON_RUNTIME" \
    --set chaosDaemon.socketPath="$CHAOS_DAEMON_SOCKET_PATH" >/dev/null

  echo "Waiting for Chaos Mesh components..."
  wait_for_deployment_ready "$CHAOS_MESH_NAMESPACE" "chaos-controller-manager" 300
  if kubectl get daemonset/chaos-daemon -n "$CHAOS_MESH_NAMESPACE" >/dev/null 2>&1; then
    wait_for_daemonset_ready "$CHAOS_MESH_NAMESPACE" "chaos-daemon" 300
  fi
  if kubectl get deployment/chaos-dashboard -n "$CHAOS_MESH_NAMESPACE" >/dev/null 2>&1; then
    wait_for_deployment_ready "$CHAOS_MESH_NAMESPACE" "chaos-dashboard" 300
  fi
}

ensure_observability_stack() {
  if observability_stack_healthy; then
    echo "Reusing healthy observability infrastructure; refreshing app telemetry env only."
    ./scripts/setup_observability.sh -n "$NAMESPACE" --skip-infra-apply
    return
  fi

  echo "Observability stack is missing or unhealthy; repairing it now..."
  ./scripts/setup_observability.sh -n "$NAMESPACE"
}

ensure_namespace() {
  if kubectl get namespace "$NAMESPACE" >/dev/null 2>&1; then
    return
  fi

  echo "Creating namespace: $NAMESPACE"
  kubectl create namespace "$NAMESPACE" >/dev/null
}

wait_for_deployment_ready() {
  local namespace="$1"
  local deploy="$2"
  local timeout_seconds="${3:-300}"
  local deadline=$((SECONDS + timeout_seconds))
  local desired available

  if kubectl rollout status deployment/"$deploy" -n "$namespace" --timeout="${timeout_seconds}s" >/dev/null 2>&1; then
    return 0
  fi

  echo "  rollout watch for deployment/$deploy was unreliable; falling back to polling..."

  while [ "$SECONDS" -lt "$deadline" ]; do
    desired=$(kubectl get deployment "$deploy" -n "$namespace" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo 0)
    available=$(kubectl get deployment "$deploy" -n "$namespace" -o jsonpath='{.status.availableReplicas}' 2>/dev/null || echo 0)
    desired=${desired:-0}
    available=${available:-0}

    if [ "$desired" -eq 0 ] || [ "$available" -ge "$desired" ]; then
      return 0
    fi

    sleep 2
  done

  echo "Timed out waiting for deployment/$deploy to become ready." >&2
  kubectl get deployment "$deploy" -n "$namespace" -o wide 2>/dev/null || true
  return 1
}

wait_for_daemonset_ready() {
  local namespace="$1"
  local daemonset="$2"
  local timeout_seconds="${3:-300}"
  local deadline=$((SECONDS + timeout_seconds))
  local desired ready updated generation observed_generation

  if kubectl rollout status daemonset/"$daemonset" -n "$namespace" --timeout="${timeout_seconds}s" >/dev/null 2>&1; then
    return 0
  fi

  echo "  rollout watch for daemonset/$daemonset was unreliable; falling back to polling..."

  while [ "$SECONDS" -lt "$deadline" ]; do
    desired=$(kubectl get daemonset "$daemonset" -n "$namespace" -o jsonpath='{.status.desiredNumberScheduled}' 2>/dev/null || echo 0)
    ready=$(kubectl get daemonset "$daemonset" -n "$namespace" -o jsonpath='{.status.numberReady}' 2>/dev/null || echo 0)
    updated=$(kubectl get daemonset "$daemonset" -n "$namespace" -o jsonpath='{.status.updatedNumberScheduled}' 2>/dev/null || echo 0)
    generation=$(kubectl get daemonset "$daemonset" -n "$namespace" -o jsonpath='{.metadata.generation}' 2>/dev/null || echo 0)
    observed_generation=$(kubectl get daemonset "$daemonset" -n "$namespace" -o jsonpath='{.status.observedGeneration}' 2>/dev/null || echo 0)

    desired=${desired:-0}
    ready=${ready:-0}
    updated=${updated:-0}
    generation=${generation:-0}
    observed_generation=${observed_generation:-0}

    if [ "$desired" -eq 0 ] || { [ "$ready" -ge "$desired" ] && [ "$updated" -ge "$desired" ] && [ "$observed_generation" -ge "$generation" ]; }; then
      return 0
    fi

    sleep 2
  done

  echo "Timed out waiting for daemonset/$daemonset to become ready." >&2
  kubectl get daemonset "$daemonset" -n "$namespace" -o wide 2>/dev/null || true
  return 1
}

scale_key_deployments() {
  local entry deploy replicas

  echo "Scaling key services for resilience..."
  for entry in "${KEY_MULTI_REPLICA_DEPLOYMENTS[@]}"; do
    deploy="${entry%%:*}"
    replicas="${entry##*:}"

    if kubectl get deployment "$deploy" -n "$NAMESPACE" >/dev/null 2>&1; then
      kubectl scale deployment/"$deploy" -n "$NAMESPACE" --replicas="$replicas" >/dev/null
      wait_for_deployment_ready "$NAMESPACE" "$deploy" 300
      echo "  deployment/$deploy scaled to $replicas"
    else
      echo "  deployment/$deploy not found, skipping"
    fi
  done
}

apply_grpc_stability_patch() {
  local deploy="$1"
  local cpu_request="$2"
  local memory_request="$3"
  local cpu_limit="$4"
  local memory_limit="$5"
  local readiness_delay="${6:-20}"
  local liveness_delay="${7:-30}"

  if ! kubectl get deployment "$deploy" -n "$NAMESPACE" >/dev/null 2>&1; then
    return
  fi

  echo "Applying stable local probe settings for $deploy..."
  kubectl patch deployment "$deploy" -n "$NAMESPACE" --type='strategic' -p "{
    \"spec\": {
      \"template\": {
        \"spec\": {
          \"containers\": [
            {
              \"name\": \"server\",
              \"readinessProbe\": {
                \"initialDelaySeconds\": ${readiness_delay},
                \"timeoutSeconds\": 5,
                \"failureThreshold\": 10,
                \"periodSeconds\": 10
              },
              \"livenessProbe\": {
                \"initialDelaySeconds\": ${liveness_delay},
                \"timeoutSeconds\": 5,
                \"failureThreshold\": 10,
                \"periodSeconds\": 10
              },
              \"resources\": {
                \"requests\": {
                  \"cpu\": \"${cpu_request}\",
                  \"memory\": \"${memory_request}\"
                },
                \"limits\": {
                  \"cpu\": \"${cpu_limit}\",
                  \"memory\": \"${memory_limit}\"
                }
              }
            }
          ]
        }
      }
    }
  }" >/dev/null
}

apply_http_frontend_stability_patch() {
  if ! kubectl get deployment frontend -n "$NAMESPACE" >/dev/null 2>&1; then
    return
  fi

  echo "Applying stable local probe settings for frontend..."
  kubectl patch deployment frontend -n "$NAMESPACE" --type='strategic' -p '{
    "spec": {
      "template": {
        "spec": {
          "containers": [
            {
              "name": "server",
              "readinessProbe": {
                "initialDelaySeconds": 20,
                "timeoutSeconds": 5,
                "failureThreshold": 10,
                "periodSeconds": 10,
                "httpGet": {
                  "path": "/_healthz",
                  "port": 8080,
                  "httpHeaders": [
                    {
                      "name": "Cookie",
                      "value": "shop_session-id=x-readiness-probe"
                    }
                  ]
                }
              },
              "livenessProbe": {
                "initialDelaySeconds": 30,
                "timeoutSeconds": 5,
                "failureThreshold": 10,
                "periodSeconds": 10,
                "httpGet": {
                  "path": "/_healthz",
                  "port": 8080,
                  "httpHeaders": [
                    {
                      "name": "Cookie",
                      "value": "shop_session-id=x-liveness-probe"
                    }
                  ]
                }
              },
              "resources": {
                "requests": {
                  "cpu": "250m",
                  "memory": "128Mi"
                },
                "limits": {
                  "cpu": "600m",
                  "memory": "256Mi"
                }
              }
            }
          ]
        }
      }
    }
  }' >/dev/null
}

capture_restart_snapshot() {
  kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | awk '{print $1 "|" $4}' | LC_ALL=C sort
}

report_cluster_health() {
  echo ""
  echo "Current deployment health:"
  kubectl get deployment -n "$NAMESPACE" 2>/dev/null || true
  echo ""
  echo "Current pod health:"
  kubectl get pods -n "$NAMESPACE" 2>/dev/null || true
  echo ""
  echo "Recent warning events:"
  kubectl get events -n "$NAMESPACE" --sort-by=.metadata.creationTimestamp 2>/dev/null | tail -n 20 || true
}

verify_deployment_availability() {
  local deploy desired available
  for deploy in "${CORE_DEPLOYMENTS[@]}"; do
    if ! kubectl get deployment "$deploy" -n "$NAMESPACE" >/dev/null 2>&1; then
      continue
    fi
    desired=$(kubectl get deployment "$deploy" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo 0)
    available=$(kubectl get deployment "$deploy" -n "$NAMESPACE" -o jsonpath='{.status.availableReplicas}' 2>/dev/null || echo 0)
    desired=${desired:-0}
    available=${available:-0}
    if [ "$available" -lt "$desired" ]; then
      echo "Deployment not fully available: $deploy (available=$available desired=$desired)" >&2
      return 1
    fi
  done
}

verify_cluster_stability() {
  local duration="${1:-45}"
  local interval=5
  local end_time=$((SECONDS + duration))
  local start_restarts end_restarts unhealthy

  echo "Verifying sustained cluster stability for ${duration}s..."
  start_restarts=$(capture_restart_snapshot || true)

  while [ "$SECONDS" -lt "$end_time" ]; do
    verify_deployment_availability || {
      report_cluster_health
      return 1
    }
    unhealthy=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | awk '$3 ~ /CrashLoopBackOff|ImagePullBackOff|ErrImagePull|CreateContainerConfigError|RunContainerError|Error|OOMKilled/ {print}')
    if [ -n "$unhealthy" ]; then
      echo "Detected unstable pods during startup:" >&2
      echo "$unhealthy" >&2
      report_cluster_health
      return 1
    fi
    sleep "$interval"
  done

  end_restarts=$(capture_restart_snapshot || true)
  if [ -n "$start_restarts" ] && [ -n "$end_restarts" ] && [ "$start_restarts" != "$end_restarts" ]; then
    echo "Pod restart counts changed during the startup stabilization window." >&2
    echo "Before:" >&2
    echo "$start_restarts" >&2
    echo "After:" >&2
    echo "$end_restarts" >&2
    report_cluster_health
    return 1
  fi
}

wait_for_local_http() {
  local name="$1"
  local url="$2"
  local header="${3:-}"
  local attempt
  for attempt in $(seq 1 20); do
    if [ -n "$header" ]; then
      if curl -fsS -H "$header" "$url" >/dev/null 2>&1; then
        echo "Verified port-forward for $name at $url"
        return 0
      fi
    else
      if curl -fsS "$url" >/dev/null 2>&1; then
        echo "Verified port-forward for $name at $url"
        return 0
      fi
    fi
    sleep 1
  done
  echo "Port-forward health check failed for $name at $url" >&2
  return 1
}

if [ ! -f "$MANIFEST" ]; then
  echo "Manifest not found: $MANIFEST" >&2
  exit 1
fi

ensure_current_cluster

ensure_chaos_mesh

ensure_namespace

mkdir -p "$RUNTIME_DIR"
mkdir -p "$PORT_FORWARD_DIR"
TS_UTC=$(date -u +"%Y%m%dT%H%M%SZ")
RUN_DIR="$RUNTIME_DIR/start_all_$TS_UTC"
mkdir -p "$RUN_DIR"

echo "Run directory: $RUN_DIR"
echo "Port-forward directory: $PORT_FORWARD_DIR"
echo "Namespace: $NAMESPACE"

echo "Applying app manifest: $MANIFEST"
kubectl apply -n "$NAMESPACE" -f "$MANIFEST"

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

  apply_grpc_stability_patch currencyservice 200m 128Mi 500m 256Mi 20 30
  apply_grpc_stability_patch productcatalogservice 200m 128Mi 500m 256Mi 20 30
  apply_grpc_stability_patch checkoutservice 250m 128Mi 600m 256Mi 20 30
  apply_grpc_stability_patch shippingservice 200m 128Mi 500m 256Mi 20 30
  apply_grpc_stability_patch recommendationservice 200m 256Mi 500m 512Mi 20 30
  apply_grpc_stability_patch paymentservice 200m 128Mi 500m 256Mi 20 30
  apply_grpc_stability_patch emailservice 200m 128Mi 500m 256Mi 20 30
  apply_grpc_stability_patch adservice 300m 256Mi 750m 512Mi 30 30
  apply_http_frontend_stability_patch
fi

scale_key_deployments

echo "Waiting for frontend deployment..."
wait_for_deployment_ready "$NAMESPACE" "frontend" 300

ensure_observability_stack

start_pf() {
  local name="$1"
  local svc="$2"
  local map="$3"
  local health_url="$4"
  local header="${5:-}"
  local log_file="$PORT_FORWARD_DIR/${name}.log"
  local pid_file="$PORT_FORWARD_DIR/${name}.pid"
  local pid=""

  if [ -f "$pid_file" ]; then
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1; then
      if wait_for_local_http "$name" "$health_url" "$header" >/dev/null 2>&1; then
        echo "Reusing managed port-forward for $name (pid $pid)"
        return
      fi
      echo "Managed port-forward for $name is stale; restarting it..."
      kill "$pid" >/dev/null 2>&1 || true
      sleep 1
    fi
    rm -f "$pid_file"
  fi

  if wait_for_local_http "$name" "$health_url" "$header" >/dev/null 2>&1; then
    echo "Reusing existing local endpoint for $name at $health_url"
    return
  fi

  kubectl port-forward -n "$NAMESPACE" "svc/$svc" "$map" >"$log_file" 2>&1 &
  echo $! >"$pid_file"
  sleep 2

  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1; then
    if wait_for_local_http "$name" "$health_url" "$header" >/dev/null 2>&1; then
      echo "Started long-lived port-forward $name -> $map (pid $pid)"
      return
    fi
    echo "Port-forward started for $name but health check failed. Check $log_file" >&2
    kill "$pid" >/dev/null 2>&1 || true
    rm -f "$pid_file"
  else
    echo "Failed to start port-forward for $name. Check $log_file" >&2
  fi
  PF_FAILED=1
}

wait_core_deployments() {
  local deploy

  echo "Waiting for core Online Boutique deployments to be available..."
  for deploy in "${CORE_DEPLOYMENTS[@]}"; do
    if kubectl get deployment "$deploy" -n "$NAMESPACE" >/dev/null 2>&1; then
      echo "  waiting on deployment/$deploy..."
      wait_for_deployment_ready "$NAMESPACE" "$deploy" 300
      echo "  deployment/$deploy ready"
    else
      echo "  deployment/$deploy not found, skipping"
    fi
  done
}

wait_core_deployments
verify_cluster_stability 45

if [ "$PF_FAILED" -ne 0 ]; then
  echo ""
  echo "One or more long-lived port-forwards failed. Check logs in: $PORT_FORWARD_DIR" >&2
  echo "Most common cause: local ports already in use (8080, 16686, 9090, 3000)." >&2
  echo "Fix: pkill -f \"kubectl port-forward\" and rerun ./scripts/start_all.sh" >&2
  exit 1
fi

echo "Starting port-forwards..."
start_pf frontend frontend "8080:80" "http://127.0.0.1:8080/_healthz" "Cookie: shop_session-id=x-readiness-probe"
start_pf jaeger jaeger "16686:16686" "http://127.0.0.1:16686/api/services"
start_pf prometheus prometheus "9090:9090" "http://127.0.0.1:9090/-/ready"
start_pf grafana grafana "3000:3000" "http://127.0.0.1:3000/api/health"

if [ "$PF_FAILED" -ne 0 ]; then
  echo ""
  echo "One or more long-lived port-forwards failed validation. Check logs in: $PORT_FORWARD_DIR" >&2
  exit 1
fi

echo "Validating telemetry sources..."
python3 ./scripts/validate_telemetry.py \
  --prom-url http://localhost:9090 \
  --jaeger-url http://localhost:16686 \
  --namespace "$NAMESPACE" \
  --require-services "frontend,checkoutservice,productcatalogservice" \
  --wait-seconds 45 \
  --poll-seconds 5 >"$RUN_DIR/telemetry_validation.json"

if [ "$ENABLE_TRAFFIC" -eq 1 ]; then
  echo "Starting synthetic traffic in background..."
  ./scripts/generate_traffic.sh -u http://localhost:8080 -d "$TRAFFIC_DURATION" -r "$TRAFFIC_RPS" -m "$TRAFFIC_MODE" >"$RUN_DIR/traffic.log" 2>&1 &
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
- Long-lived observability/access forwards: $PORT_FORWARD_DIR

To stop port-forwards quickly:
  kill \
    \\$(cat $PORT_FORWARD_DIR/frontend.pid) \
    \\$(cat $PORT_FORWARD_DIR/jaeger.pid) \
    \\$(cat $PORT_FORWARD_DIR/prometheus.pid) \
    \\$(cat $PORT_FORWARD_DIR/grafana.pid)
DONE
