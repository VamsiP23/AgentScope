#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="default"
DEPLOYMENT="checkoutservice"
DURATION=0
ACTION=""
ANN_KEY="agentscope.io/original-replicas"

usage() {
  cat <<USAGE
Simulate a service outage by scaling one deployment to zero replicas.

Usage:
  $(basename "$0") <apply|revert|status> [options]

Options:
  -n <namespace>     Kubernetes namespace (default: default)
  -s <deployment>    Deployment to affect (default: checkoutservice)
  -d <seconds>       Auto-revert after N seconds (apply only, default: 0 = no auto-revert)
  -h                 Show this help

Examples:
  ./scripts/service_outage.sh apply -n default -s checkoutservice -d 120
  ./scripts/service_outage.sh revert -n default -s checkoutservice
  ./scripts/service_outage.sh status -n default -s checkoutservice
USAGE
}

require_kubectl() {
  if ! command -v kubectl >/dev/null 2>&1; then
    echo "kubectl is required but not installed." >&2
    exit 1
  fi
}

deployment_exists() {
  kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" >/dev/null 2>&1
}

get_replicas() {
  kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}'
}

get_annotation() {
  kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" -o "jsonpath={.metadata.annotations.agentscope\\.io/original-replicas}" 2>/dev/null || true
}

apply_outage() {
  local current
  current="$(get_replicas)"
  kubectl annotate deployment "$DEPLOYMENT" -n "$NAMESPACE" "$ANN_KEY=$current" --overwrite >/dev/null
  kubectl scale deployment "$DEPLOYMENT" -n "$NAMESPACE" --replicas=0 >/dev/null
  echo "Applied outage: deployment/$DEPLOYMENT scaled from $current to 0 in namespace $NAMESPACE."
}

revert_outage() {
  local original
  original="$(get_annotation)"
  if [ -z "${original:-}" ]; then
    original=1
  fi
  kubectl scale deployment "$DEPLOYMENT" -n "$NAMESPACE" --replicas="$original" >/dev/null
  kubectl annotate deployment "$DEPLOYMENT" -n "$NAMESPACE" "$ANN_KEY-" >/dev/null 2>&1 || true
  echo "Reverted outage: deployment/$DEPLOYMENT scaled to $original in namespace $NAMESPACE."
}

show_status() {
  local replicas ready
  replicas="$(kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}')"
  ready="$(kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}')"
  ready="${ready:-0}"
  echo "deployment=$DEPLOYMENT namespace=$NAMESPACE replicas=$replicas ready_replicas=$ready"
}

if [ "$#" -lt 1 ]; then
  usage
  exit 1
fi

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

ACTION="$1"
shift

while getopts ":n:s:d:h" opt; do
  case "$opt" in
    n) NAMESPACE="$OPTARG" ;;
    s) DEPLOYMENT="$OPTARG" ;;
    d) DURATION="$OPTARG" ;;
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

if ! [[ "$DURATION" =~ ^[0-9]+$ ]]; then
  echo "Duration must be a non-negative integer." >&2
  exit 1
fi

require_kubectl

if ! deployment_exists; then
  echo "Deployment not found: $DEPLOYMENT (namespace: $NAMESPACE)" >&2
  exit 1
fi

case "$ACTION" in
  apply)
    apply_outage
    if [ "$DURATION" -gt 0 ]; then
      echo "Holding outage for ${DURATION}s..."
      sleep "$DURATION"
      revert_outage
      echo "Auto-reverted outage."
    else
      echo "Outage remains active. Revert with:"
      echo "  ./scripts/service_outage.sh revert -n $NAMESPACE -s $DEPLOYMENT"
    fi
    ;;
  revert)
    revert_outage
    ;;
  status)
    show_status
    ;;
  *)
    echo "Unknown action: $ACTION" >&2
    usage
    exit 1
    ;;
esac
