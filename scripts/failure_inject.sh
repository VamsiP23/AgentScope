#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="default"
ACTION=""
SCENARIO=""
DURATION=0
TARGET=""
LATENCY="3s"

SCRIPT_NAME="$(basename "$0")"
ANN_PREFIX="agentscope.io"

usage() {
  cat <<USAGE
Inject and revert deterministic failure scenarios for Online Boutique.

Usage:
  $SCRIPT_NAME <apply|revert> <scenario> [options]

Scenarios:
  service_outage      Scale a deployment to zero replicas.
  dependency_outage   Scale redis-cart to zero replicas.
  latency_spike       Set EXTRA_LATENCY on productcatalogservice.
  cpu_pressure        Trigger productcatalogservice CPU-heavy mode (USR1/USR2).

Options:
  -n <namespace>      Kubernetes namespace (default: default)
  -d <seconds>        Auto-revert after N seconds (apply only, default: 0 = no auto-revert)
  -t <deployment>     Target deployment for service_outage (default: checkoutservice)
  -l <duration>       EXTRA_LATENCY value for latency_spike (default: 3s)
  -h                  Show this help

Examples:
  $SCRIPT_NAME apply service_outage -n default -t checkoutservice -d 120
  $SCRIPT_NAME revert service_outage -n default -t checkoutservice
  $SCRIPT_NAME apply dependency_outage -n default -d 120
  $SCRIPT_NAME apply latency_spike -n default -l 5s -d 180
  $SCRIPT_NAME apply cpu_pressure -n default -d 180
USAGE
}

require_kubectl() {
  if ! command -v kubectl >/dev/null 2>&1; then
    echo "kubectl is required but not installed." >&2
    exit 1
  fi
}

set_annotation() {
  local deploy="$1"
  local key="$2"
  local value="$3"
  kubectl annotate deployment "$deploy" -n "$NAMESPACE" "$key=$value" --overwrite >/dev/null
}

remove_annotation() {
  local deploy="$1"
  local key="$2"
  kubectl annotate deployment "$deploy" -n "$NAMESPACE" "$key-" >/dev/null 2>&1 || true
}

get_annotation() {
  local deploy="$1"
  local key="$2"
  kubectl get deployment "$deploy" -n "$NAMESPACE" -o "jsonpath={.metadata.annotations.$key}" 2>/dev/null || true
}

scale_down_with_backup() {
  local deploy="$1"
  local key="${ANN_PREFIX}/original-replicas"
  local current

  current="$(kubectl get deployment "$deploy" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}')"
  set_annotation "$deploy" "$key" "$current"
  kubectl scale deployment "$deploy" -n "$NAMESPACE" --replicas=0
  echo "Scaled deployment/$deploy from $current to 0 replicas."
}

restore_scale_from_backup() {
  local deploy="$1"
  local key="${ANN_PREFIX}/original-replicas"
  local original

  original="$(get_annotation "$deploy" "agentscope\.io/original-replicas")"
  if [ -z "${original:-}" ]; then
    original=1
  fi
  kubectl scale deployment "$deploy" -n "$NAMESPACE" --replicas="$original"
  remove_annotation "$deploy" "$key"
  echo "Restored deployment/$deploy replicas to $original."
}

apply_service_outage() {
  local deploy="${TARGET:-checkoutservice}"
  scale_down_with_backup "$deploy"
}

revert_service_outage() {
  local deploy="${TARGET:-checkoutservice}"
  restore_scale_from_backup "$deploy"
}

apply_dependency_outage() {
  TARGET="redis-cart"
  scale_down_with_backup "$TARGET"
}

revert_dependency_outage() {
  TARGET="redis-cart"
  restore_scale_from_backup "$TARGET"
}

apply_latency_spike() {
  local deploy="productcatalogservice"
  local key="${ANN_PREFIX}/original-extra-latency"
  local current

  current="$(kubectl get deployment "$deploy" -n "$NAMESPACE" -o jsonpath="{.spec.template.spec.containers[?(@.name=='server')].env[?(@.name=='EXTRA_LATENCY')].value}")"
  if [ -z "$current" ]; then
    current="__unset__"
  fi
  set_annotation "$deploy" "$key" "$current"
  kubectl set env deployment/"$deploy" -n "$NAMESPACE" EXTRA_LATENCY="$LATENCY" >/dev/null
  echo "Set EXTRA_LATENCY=$LATENCY on deployment/$deploy."
}

revert_latency_spike() {
  local deploy="productcatalogservice"
  local key="${ANN_PREFIX}/original-extra-latency"
  local original

  original="$(get_annotation "$deploy" "agentscope\.io/original-extra-latency")"
  if [ -z "${original:-}" ] || [ "$original" = "__unset__" ]; then
    kubectl set env deployment/"$deploy" -n "$NAMESPACE" EXTRA_LATENCY- >/dev/null
    echo "Unset EXTRA_LATENCY on deployment/$deploy."
  else
    kubectl set env deployment/"$deploy" -n "$NAMESPACE" EXTRA_LATENCY="$original" >/dev/null
    echo "Restored EXTRA_LATENCY=$original on deployment/$deploy."
  fi
  remove_annotation "$deploy" "$key"
}

signal_productcatalog() {
  local sig="$1"
  local pod
  pod="$(kubectl get pods -n "$NAMESPACE" -l app=productcatalogservice -o jsonpath='{.items[0].metadata.name}')"
  if [ -z "$pod" ]; then
    echo "No productcatalogservice pod found in namespace $NAMESPACE" >&2
    exit 1
  fi
  kubectl exec -n "$NAMESPACE" "$pod" -c server -- kill "-$sig" 1 >/dev/null
}

apply_cpu_pressure() {
  signal_productcatalog "USR1"
  echo "Triggered CPU pressure mode on productcatalogservice (USR1)."
}

revert_cpu_pressure() {
  signal_productcatalog "USR2"
  echo "Reverted CPU pressure mode on productcatalogservice (USR2)."
}

dispatch_apply() {
  case "$SCENARIO" in
    service_outage) apply_service_outage ;;
    dependency_outage) apply_dependency_outage ;;
    latency_spike) apply_latency_spike ;;
    cpu_pressure) apply_cpu_pressure ;;
    *)
      echo "Unknown scenario: $SCENARIO" >&2
      usage
      exit 1
      ;;
  esac
}

dispatch_revert() {
  case "$SCENARIO" in
    service_outage) revert_service_outage ;;
    dependency_outage) revert_dependency_outage ;;
    latency_spike) revert_latency_spike ;;
    cpu_pressure) revert_cpu_pressure ;;
    *)
      echo "Unknown scenario: $SCENARIO" >&2
      usage
      exit 1
      ;;
  esac
}

if [ "$#" -lt 2 ]; then
  usage
  exit 1
fi

ACTION="$1"
SCENARIO="$2"
shift 2

while getopts ":n:d:t:l:h" opt; do
  case "$opt" in
    n) NAMESPACE="$OPTARG" ;;
    d) DURATION="$OPTARG" ;;
    t) TARGET="$OPTARG" ;;
    l) LATENCY="$OPTARG" ;;
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

case "$ACTION" in
  apply)
    dispatch_apply
    if [ "$DURATION" -gt 0 ]; then
      echo "Holding scenario '$SCENARIO' for ${DURATION}s..."
      sleep "$DURATION"
      dispatch_revert
      echo "Auto-reverted scenario '$SCENARIO'."
    else
      echo "Scenario '$SCENARIO' applied. Revert with:"
      echo "  ./$SCRIPT_NAME revert $SCENARIO -n $NAMESPACE ${TARGET:+-t $TARGET}"
    fi
    ;;
  revert)
    dispatch_revert
    ;;
  *)
    echo "Unknown action: $ACTION" >&2
    usage
    exit 1
    ;;
esac
