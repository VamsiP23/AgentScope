#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="default"
APPLY_INFRA=1

usage() {
  cat <<USAGE
Set up local observability stack for Online Boutique on Kubernetes.

Usage:
  $(basename "$0") [-n namespace] [--skip-infra-apply]

Options:
  -n   Kubernetes namespace where Online Boutique is deployed (default: default)
  --skip-infra-apply
       Skip applying observability manifests and only patch app deployments/env vars
  -h   Show this help
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    -n)
      NAMESPACE="${2:-}"
      if [ -z "$NAMESPACE" ]; then
        echo "Missing argument for -n" >&2
        exit 1
      fi
      shift 2
      ;;
    --skip-infra-apply)
      APPLY_INFRA=0
      shift
      ;;
    -h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required but not installed." >&2
  exit 1
fi

wait_for_deployment_ready() {
  local namespace="$1"
  local deploy="$2"
  local timeout_seconds="${3:-300}"
  local deadline=$((SECONDS + timeout_seconds))
  local desired available updated generation observed_generation

  if kubectl rollout status deployment/"$deploy" -n "$namespace" --timeout="${timeout_seconds}s" >/dev/null 2>&1; then
    return 0
  fi

  echo "  rollout watch for deployment/$deploy was unreliable; falling back to polling..."

  while [ "$SECONDS" -lt "$deadline" ]; do
    desired=$(kubectl get deployment "$deploy" -n "$namespace" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo 0)
    available=$(kubectl get deployment "$deploy" -n "$namespace" -o jsonpath='{.status.availableReplicas}' 2>/dev/null || echo 0)
    updated=$(kubectl get deployment "$deploy" -n "$namespace" -o jsonpath='{.status.updatedReplicas}' 2>/dev/null || echo 0)
    generation=$(kubectl get deployment "$deploy" -n "$namespace" -o jsonpath='{.metadata.generation}' 2>/dev/null || echo 0)
    observed_generation=$(kubectl get deployment "$deploy" -n "$namespace" -o jsonpath='{.status.observedGeneration}' 2>/dev/null || echo 0)

    desired=${desired:-0}
    available=${available:-0}
    updated=${updated:-0}
    generation=${generation:-0}
    observed_generation=${observed_generation:-0}

    if [ "$desired" -eq 0 ] || { [ "$available" -ge "$desired" ] && [ "$updated" -ge "$desired" ] && [ "$observed_generation" -ge "$generation" ]; }; then
      return 0
    fi

    sleep 2
  done

  echo "Timed out waiting for deployment/$deploy to become ready." >&2
  kubectl get deployment "$deploy" -n "$namespace" -o wide 2>/dev/null || true
  return 1
}

if [ "$APPLY_INFRA" -eq 1 ]; then
  echo "Applying observability components to namespace: $NAMESPACE"
  for manifest in observability/manifests/*.yaml; do
    kubectl apply -n "$NAMESPACE" -f "$manifest"
  done
else
  echo "Skipping observability manifest apply; reusing existing observability infrastructure."
fi

DEPLOYMENTS=(
  adservice
  cartservice
  checkoutservice
  currencyservice
  emailservice
  frontend
  paymentservice
  productcatalogservice
  recommendationservice
  shippingservice
)

echo "Enabling tracing/stats env vars on Online Boutique deployments (if present)..."
for deploy in "${DEPLOYMENTS[@]}"; do
  if kubectl get deployment "$deploy" -n "$NAMESPACE" >/dev/null 2>&1; then
    kubectl set env deployment/"$deploy" -n "$NAMESPACE" \
      ENABLE_TRACING=1 \
      ENABLE_STATS=1 \
      COLLECTOR_SERVICE_ADDR=opentelemetrycollector:4317 \
      OTEL_SERVICE_NAME="$deploy" \
      OTEL_RESOURCE_ATTRIBUTES="service.name=$deploy,deployment.environment=local"
    echo "  patched deployment/$deploy"
    wait_for_deployment_ready "$NAMESPACE" "$deploy" 300
    echo "  rollout complete for deployment/$deploy"
  else
    echo "  skipped deployment/$deploy (not found)"
  fi
done

if [ "$APPLY_INFRA" -eq 1 ]; then
  echo ""
  echo "Waiting for observability deployments..."
  wait_for_deployment_ready "$NAMESPACE" "opentelemetrycollector" 180
  wait_for_deployment_ready "$NAMESPACE" "jaeger" 180
  wait_for_deployment_ready "$NAMESPACE" "prometheus" 180
  wait_for_deployment_ready "$NAMESPACE" "grafana" 180
  wait_for_deployment_ready "$NAMESPACE" "kube-state-metrics" 180
fi

echo ""
echo "Observability setup complete."
echo "Port-forward UIs in separate terminals:"
echo "  kubectl port-forward -n $NAMESPACE svc/jaeger 16686:16686"
echo "  kubectl port-forward -n $NAMESPACE svc/prometheus 9090:9090"
echo "  kubectl port-forward -n $NAMESPACE svc/grafana 3000:3000"
echo ""
echo "Grafana login: admin / admin"
