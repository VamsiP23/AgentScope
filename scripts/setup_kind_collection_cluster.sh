#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="agentscope-collection"
NAMESPACE="default"
KIND_CONFIG="configs/kind-agentscope-collection.yaml"
MANIFEST="vendor/microservices-demo/release/kubernetes-manifests.yaml"
RENDERED_MANIFEST=".runtime/kind_collection_manifest.yaml"
DELETE_EXISTING=0
SKIP_DEPLOY=0
SKIP_IMAGE_LOAD=0
STABILITY_SECONDS=45

usage() {
  cat <<USAGE
Create and prepare a kind cluster for AgentScope native episode collection.

Usage:
  $(basename "$0") [options]

Options:
  -n <namespace>    Kubernetes namespace (default: default)
  -c <cluster>      kind cluster name (default: agentscope-collection)
  -f <config>       kind config path (default: configs/kind-agentscope-collection.yaml)
  -m <manifest>     Online Boutique manifest path
  -d                Delete and recreate the kind cluster if it already exists
  -s                Skip app/observability deploy; only switch context and expose services
  -i                Skip loading locally cached images into kind
  -h                Show help

Exposed local endpoints:
  frontend      http://localhost:8080
  Prometheus    http://localhost:9090
  Jaeger        http://localhost:16686
  Grafana       http://localhost:3000
USAGE
}

while getopts ":n:c:f:m:dsih" opt; do
  case "$opt" in
    n) NAMESPACE="$OPTARG" ;;
    c) CLUSTER_NAME="$OPTARG" ;;
    f) KIND_CONFIG="$OPTARG" ;;
    m) MANIFEST="$OPTARG" ;;
    d) DELETE_EXISTING=1 ;;
    s) SKIP_DEPLOY=1 ;;
    i) SKIP_IMAGE_LOAD=1 ;;
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

require_binary() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "$name is required but not installed." >&2
    exit 1
  fi
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

kill_port_forwards() {
  echo "Stopping local kubectl port-forwards so kind can own fixed host ports..."
  pkill -f "kubectl port-forward" >/dev/null 2>&1 || true
  rm -rf .runtime/port_forwards
}

cluster_exists() {
  kind get clusters | grep -Fxq "$CLUSTER_NAME"
}

wait_deployment() {
  local deployment="$1"
  local timeout="${2:-300s}"
  if kubectl get deployment "$deployment" -n "$NAMESPACE" >/dev/null 2>&1; then
    kubectl rollout status deployment/"$deployment" -n "$NAMESPACE" --timeout="$timeout"
  fi
}

wait_core_deployments() {
  local deployments=(
    adservice
    cartservice
    checkoutservice
    currencyservice
    emailservice
    frontend
    paymentservice
    productcatalogservice
    recommendationservice
    redis-cart
    shippingservice
    opentelemetrycollector
    kube-state-metrics
    jaeger
    prometheus
    grafana
  )
  local deployment
  for deployment in "${deployments[@]}"; do
    wait_deployment "$deployment" 900s
  done
}

patch_nodeport_service() {
  local service="$1"
  local service_port="$2"
  local target_port="$3"
  local node_port="$4"
  local port_name="${5:-web}"

  if ! kubectl get service "$service" -n "$NAMESPACE" >/dev/null 2>&1; then
    echo "Service $service is not present yet; skipping NodePort patch"
    return
  fi

  kubectl patch service "$service" -n "$NAMESPACE" --type=merge -p "{
    \"spec\": {
      \"type\": \"NodePort\",
      \"ports\": [
        {
          \"name\": \"${port_name}\",
          \"port\": ${service_port},
          \"targetPort\": ${target_port},
          \"nodePort\": ${node_port}
        }
      ]
    }
  }" >/dev/null
}

patch_observability_nodeports() {
  echo "Exposing collection services through fixed kind NodePorts..."
  patch_nodeport_service frontend-external 80 8080 30080 http
  patch_nodeport_service prometheus 9090 9090 30090 web
  patch_nodeport_service grafana 3000 3000 30300 web

  if kubectl get service jaeger -n "$NAMESPACE" >/dev/null 2>&1; then
    kubectl patch service jaeger -n "$NAMESPACE" --type=merge -p '{
      "spec": {
        "type": "NodePort",
        "ports": [
          {"name": "ui", "port": 16686, "targetPort": 16686, "nodePort": 30686},
          {"name": "otlp-grpc", "port": 4317, "targetPort": 4317},
          {"name": "otlp-http", "port": 4318, "targetPort": 4318}
        ]
      }
    }' >/dev/null
  fi
}

verify_http() {
  local name="$1"
  local url="$2"
  local attempts="${3:-30}"
  local try

  for try in $(seq 1 "$attempts"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "Verified $name at $url"
      return
    fi
    sleep 2
  done

  echo "Timed out waiting for $name at $url" >&2
  return 1
}

load_cached_images() {
  if [ "$SKIP_IMAGE_LOAD" -eq 1 ]; then
    return
  fi

  local images=(
    us-central1-docker.pkg.dev/google-samples/microservices-demo/adservice:v0.10.4
    us-central1-docker.pkg.dev/google-samples/microservices-demo/cartservice:v0.10.4
    us-central1-docker.pkg.dev/google-samples/microservices-demo/checkoutservice:v0.10.4
    us-central1-docker.pkg.dev/google-samples/microservices-demo/currencyservice:v0.10.4
    us-central1-docker.pkg.dev/google-samples/microservices-demo/emailservice:v0.10.4
    us-central1-docker.pkg.dev/google-samples/microservices-demo/frontend:v0.10.4
    us-central1-docker.pkg.dev/google-samples/microservices-demo/loadgenerator:v0.10.4
    us-central1-docker.pkg.dev/google-samples/microservices-demo/paymentservice:v0.10.4
    us-central1-docker.pkg.dev/google-samples/microservices-demo/productcatalogservice:v0.10.4
    us-central1-docker.pkg.dev/google-samples/microservices-demo/recommendationservice:v0.10.4
    us-central1-docker.pkg.dev/google-samples/microservices-demo/shippingservice:v0.10.4
    redis:alpine
    prom/prometheus:v2.52.0
    jaegertracing/all-in-one:1.57
    registry.k8s.io/kube-state-metrics/kube-state-metrics:v2.13.0
    otel/opentelemetry-collector-contrib:0.96.0
    grafana/grafana:11.0.0
  )

  echo "Loading cached images into kind cluster when present locally..."
  local image
  for image in "${images[@]}"; do
    if docker image inspect "$image" >/dev/null 2>&1; then
      echo "  loading $image"
      kind load docker-image "$image" --name "$CLUSTER_NAME" >/dev/null
    else
      echo "  local image not found, kind will pull if needed: $image"
    fi
  done
}

verify_cluster() {
  echo "Verifying kind collection cluster..."
  kubectl get nodes -o wide
  kubectl get pods -n "$NAMESPACE"
  kubectl get configmap,pod,job -n "$NAMESPACE" -l agentscope.dev/native-fault=true -o name
  verify_http frontend http://localhost:8080/_healthz
  verify_http prometheus http://localhost:9090/-/ready
  verify_http jaeger http://localhost:16686/api/services
}

require_binary kind
require_binary kubectl
require_binary docker
require_binary curl

[ -f "$KIND_CONFIG" ] || { echo "kind config not found: $KIND_CONFIG" >&2; exit 1; }
[ -f "$MANIFEST" ] || { echo "manifest not found: $MANIFEST" >&2; exit 1; }

if [ "$DELETE_EXISTING" -eq 1 ] && cluster_exists; then
  echo "Deleting existing kind cluster: $CLUSTER_NAME"
  kind delete cluster --name "$CLUSTER_NAME"
fi

kill_port_forwards

if ! cluster_exists; then
  echo "Creating kind cluster: $CLUSTER_NAME"
  kind create cluster --config "$KIND_CONFIG" --name "$CLUSTER_NAME"
else
  echo "Reusing existing kind cluster: $CLUSTER_NAME"
fi

kubectl config use-context "kind-${CLUSTER_NAME}" >/dev/null
retry_cmd 5 5 kubectl wait --for=condition=Ready nodes --all --timeout=180s >/dev/null
load_cached_images

if [ "$SKIP_DEPLOY" -ne 1 ]; then
  echo "Rendering stable kind collection manifest..."
  python3 scripts/render_kind_collection_manifest.py \
    --app-manifest "$MANIFEST" \
    --namespace "$NAMESPACE" \
    --out "$RENDERED_MANIFEST" >/dev/null
  echo "Applying rendered manifest: $RENDERED_MANIFEST"
  kubectl apply -n "$NAMESPACE" -f "$RENDERED_MANIFEST"
  wait_core_deployments
fi

verify_cluster

python3 scripts/repair_observability_access.py \
  --namespace "$NAMESPACE" \
  --frontend-url http://localhost:8080 \
  --prom-url http://localhost:9090 \
  --jaeger-url http://localhost:16686

echo ""
echo "kind collection cluster is ready."
echo "Use context: kind-${CLUSTER_NAME}"
echo "Frontend:   http://localhost:8080"
echo "Prometheus: http://localhost:9090"
echo "Jaeger:     http://localhost:16686"
