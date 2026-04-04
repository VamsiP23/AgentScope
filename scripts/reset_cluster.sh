#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="default"
MANIFEST="vendor/microservices-demo/release/kubernetes-manifests.yaml"
KUBE_CONTEXT=""
KILL_PORT_FORWARDS=0
REFRESH_OBSERVABILITY=0
DISABLE_BUILTIN_LOADGEN=1
STABLE_LOCAL_MODE=1
CHAOS_MESH_NAMESPACE="chaos-mesh"
CHAOS_RESOURCE_TYPES=(
  podchaos
  stresschaos
  networkchaos
  dnschaos
  httpchaos
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
KEY_MULTI_REPLICA_DEPLOYMENTS=(
  frontend:2
  cartservice:2
  checkoutservice:2
  productcatalogservice:2
)
STABILITY_WINDOW_SECONDS=45

usage() {
  cat <<USAGE
Reset the local cluster to a clean AgentScope baseline.

Usage:
  $(basename "$0") [options]

Options:
  -n <namespace>   Kubernetes namespace (default: default)
  -m <manifest>    App manifest path (default: vendor/microservices-demo/release/kubernetes-manifests.yaml)
  -c <context>     Use this existing kubectl context (example: docker-desktop)
  -p               Kill local kubectl port-forwards before reset
  -o               Reapply observability stack during reset
  -h               Show help
USAGE
}

while getopts ":n:m:c:poh" opt; do
  case "$opt" in
    n) NAMESPACE="$OPTARG" ;;
    m) MANIFEST="$OPTARG" ;;
    c) KUBE_CONTEXT="$OPTARG" ;;
    p) KILL_PORT_FORWARDS=1 ;;
    o) REFRESH_OBSERVABILITY=1 ;;
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

use_context() {
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

  echo "Using kubectl context: $context_name"
  kubectl config use-context "$context_name" >/dev/null
  kubectl wait --for=condition=Ready nodes --all --timeout=180s >/dev/null
}

kill_port_forwards() {
  if [ "$KILL_PORT_FORWARDS" -ne 1 ]; then
    return
  fi
  echo "Stopping local kubectl port-forwards..."
  pkill -f "kubectl port-forward" >/dev/null 2>&1 || true
}

cleanup_chaos() {
  local resource
  echo "Removing lingering Chaos Mesh resources from namespace: $NAMESPACE"
  for resource in "${CHAOS_RESOURCE_TYPES[@]}"; do
    kubectl delete "$resource" --all -n "$NAMESPACE" --ignore-not-found --timeout=120s >/dev/null 2>&1 || true
  done
}

ensure_namespace() {
  if ! kubectl get namespace "$NAMESPACE" >/dev/null 2>&1; then
    kubectl create namespace "$NAMESPACE" >/dev/null
  fi
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

scale_key_deployments() {
  local entry deploy replicas
  for entry in "${KEY_MULTI_REPLICA_DEPLOYMENTS[@]}"; do
    deploy="${entry%%:*}"
    replicas="${entry##*:}"
    if kubectl get deployment "$deploy" -n "$NAMESPACE" >/dev/null 2>&1; then
      kubectl scale deployment/"$deploy" -n "$NAMESPACE" --replicas="$replicas" >/dev/null
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
  }" >/dev/null || true
}

apply_http_frontend_stability_patch() {
  if ! kubectl get deployment/frontend -n "$NAMESPACE" >/dev/null 2>&1; then
    return
  fi

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
  }' >/dev/null || true
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
  local duration="${1:-$STABILITY_WINDOW_SECONDS}"
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
      echo "Detected unstable pods during reset:" >&2
      echo "$unhealthy" >&2
      report_cluster_health
      return 1
    fi
    sleep "$interval"
  done

  end_restarts=$(capture_restart_snapshot || true)
  if [ -n "$start_restarts" ] && [ -n "$end_restarts" ] && [ "$start_restarts" != "$end_restarts" ]; then
    echo "Pod restart counts changed during the reset stabilization window." >&2
    echo "Before:" >&2
    echo "$start_restarts" >&2
    echo "After:" >&2
    echo "$end_restarts" >&2
    report_cluster_health
    return 1
  fi
}

apply_stable_local_patches() {
  if [ "$STABLE_LOCAL_MODE" -ne 1 ]; then
    return
  fi

  if kubectl get deployment/cartservice -n "$NAMESPACE" >/dev/null 2>&1; then
    kubectl patch deployment cartservice -n "$NAMESPACE" --type='json' -p='[
      {"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/initialDelaySeconds","value":45},
      {"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/timeoutSeconds","value":10},
      {"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/failureThreshold","value":20},
      {"op":"remove","path":"/spec/template/spec/containers/0/livenessProbe"},
      {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/cpu","value":"300m"},
      {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"128Mi"},
      {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/cpu","value":"1000m"},
      {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"512Mi"}
    ]' >/dev/null || true
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
}

wait_core_deployments() {
  local deploy
  echo "Waiting for core deployments..."
  for deploy in "${CORE_DEPLOYMENTS[@]}"; do
    if kubectl get deployment "$deploy" -n "$NAMESPACE" >/dev/null 2>&1; then
      echo "  waiting on deployment/$deploy..."
      wait_for_deployment_ready "$NAMESPACE" "$deploy" 300
      echo "  deployment/$deploy ready"
    fi
  done
}

require_service_endpoints() {
  local svc addresses
  for svc in frontend jaeger prometheus grafana kube-state-metrics; do
    if ! kubectl get svc "$svc" -n "$NAMESPACE" >/dev/null 2>&1; then
      echo "Required service missing: $svc" >&2
      exit 1
    fi
    addresses=$(kubectl get endpoints "$svc" -n "$NAMESPACE" -o jsonpath='{.subsets[*].addresses[*].ip}' 2>/dev/null || true)
    if [ -z "$addresses" ]; then
      echo "Service has no ready endpoints: $svc" >&2
      exit 1
    fi
  done
}

require_chaos_mesh_health() {
  local ready
  ready=$(kubectl get deploy chaos-controller-manager -n "$CHAOS_MESH_NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || true)
  if [ -z "$ready" ] || [ "$ready" = "0" ]; then
    echo "Chaos Mesh controller is not ready." >&2
    exit 1
  fi
}

require_binary kubectl
[ -f "$MANIFEST" ] || { echo "Manifest not found: $MANIFEST" >&2; exit 1; }

use_context
kill_port_forwards
ensure_namespace
cleanup_chaos

echo "Reapplying app manifest: $MANIFEST"
kubectl apply -n "$NAMESPACE" -f "$MANIFEST" >/dev/null

if [ "$DISABLE_BUILTIN_LOADGEN" -eq 1 ] && kubectl get deployment/loadgenerator -n "$NAMESPACE" >/dev/null 2>&1; then
  kubectl scale deployment/loadgenerator -n "$NAMESPACE" --replicas=0 >/dev/null
fi

apply_stable_local_patches
scale_key_deployments

if [ "$REFRESH_OBSERVABILITY" -eq 1 ]; then
  echo "Reapplying observability stack..."
  ./scripts/setup_observability.sh -n "$NAMESPACE" >/dev/null
else
  echo "Observability stack refresh skipped; reusing existing session observability."
fi

wait_core_deployments
require_service_endpoints
require_chaos_mesh_health
verify_cluster_stability "$STABILITY_WINDOW_SECONDS"

echo "Cluster reset complete."
