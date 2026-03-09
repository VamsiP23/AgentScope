#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="default"

usage() {
  cat <<USAGE
Set up local observability stack for Online Boutique on Kubernetes.

Usage:
  $(basename "$0") [-n namespace]

Options:
  -n   Kubernetes namespace where Online Boutique is deployed (default: default)
  -h   Show this help
USAGE
}

while getopts ":n:h" opt; do
  case "$opt" in
    n) NAMESPACE="$OPTARG" ;;
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

echo "Applying observability components to namespace: $NAMESPACE"
for manifest in observability/manifests/*.yaml; do
  kubectl apply -n "$NAMESPACE" -f "$manifest"
done

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
    kubectl rollout status deployment/"$deploy" -n "$NAMESPACE" --timeout=300s >/dev/null
    echo "  rollout complete for deployment/$deploy"
  else
    echo "  skipped deployment/$deploy (not found)"
  fi
done

echo ""
echo "Waiting for observability deployments..."
kubectl rollout status deployment/opentelemetrycollector -n "$NAMESPACE" --timeout=180s
kubectl rollout status deployment/jaeger -n "$NAMESPACE" --timeout=180s
kubectl rollout status deployment/prometheus -n "$NAMESPACE" --timeout=180s
kubectl rollout status deployment/grafana -n "$NAMESPACE" --timeout=180s

echo ""
echo "Observability setup complete."
echo "Port-forward UIs in separate terminals:"
echo "  kubectl port-forward -n $NAMESPACE svc/jaeger 16686:16686"
echo "  kubectl port-forward -n $NAMESPACE svc/prometheus 9090:9090"
echo "  kubectl port-forward -n $NAMESPACE svc/grafana 3000:3000"
echo ""
echo "Grafana login: admin / admin"
