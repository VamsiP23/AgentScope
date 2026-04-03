#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-}"
NAMESPACE="${NAMESPACE:-default}"
DEPLOYMENT="${DEPLOYMENT:-productcatalogservice}"
CONTAINER="${CONTAINER:-server}"
GOOD_IMAGE="${GOOD_IMAGE:-us-central1-docker.pkg.dev/google-samples/microservices-demo/productcatalogservice:v0.10.4}"
BAD_IMAGE="${BAD_IMAGE:-us-central1-docker.pkg.dev/google-samples/microservices-demo/productcatalogservice:not-a-real-tag}"
FORCE_RECREATE="${FORCE_RECREATE:-false}"
RESTORE_STRATEGY_TYPE="${RESTORE_STRATEGY_TYPE:-RollingUpdate}"
RESTORE_MAX_SURGE="${RESTORE_MAX_SURGE:-25%}"
RESTORE_MAX_UNAVAILABLE="${RESTORE_MAX_UNAVAILABLE:-25%}"
APPLY_WAIT_TIMEOUT_SECONDS="${APPLY_WAIT_TIMEOUT_SECONDS:-5}"

usage() {
  cat <<USAGE
Apply or revert a bad rollout fault on a deployment.

Usage:
  $(basename "$0") apply|revert

Environment overrides:
  NAMESPACE
  DEPLOYMENT
  CONTAINER
  GOOD_IMAGE
  BAD_IMAGE
USAGE
}

if [ -z "$ACTION" ]; then
  usage
  exit 1
fi

case "$ACTION" in
  apply)
    echo "Applying bad rollout to deployment/$DEPLOYMENT in namespace $NAMESPACE"
    if [ "$FORCE_RECREATE" = "true" ]; then
      kubectl patch deployment/"$DEPLOYMENT" -n "$NAMESPACE" --type merge -p \
        '{"spec":{"strategy":{"type":"Recreate","rollingUpdate":null}}}' >/dev/null
    fi
    kubectl set image deployment/"$DEPLOYMENT" -n "$NAMESPACE" "$CONTAINER=$BAD_IMAGE" >/dev/null
    if [ "${APPLY_WAIT_TIMEOUT_SECONDS:-0}" -gt 0 ] 2>/dev/null; then
      kubectl rollout status deployment/"$DEPLOYMENT" -n "$NAMESPACE" \
        --timeout="${APPLY_WAIT_TIMEOUT_SECONDS}s" >/dev/null 2>&1 || true
    fi
    ;;
  revert)
    echo "Reverting bad rollout on deployment/$DEPLOYMENT in namespace $NAMESPACE"
    kubectl set image deployment/"$DEPLOYMENT" -n "$NAMESPACE" "$CONTAINER=$GOOD_IMAGE" >/dev/null
    kubectl rollout status deployment/"$DEPLOYMENT" -n "$NAMESPACE" --timeout=300s >/dev/null
    if [ "$FORCE_RECREATE" = "true" ]; then
      if [ "$RESTORE_STRATEGY_TYPE" = "RollingUpdate" ]; then
        kubectl patch deployment/"$DEPLOYMENT" -n "$NAMESPACE" --type merge -p \
          "{\"spec\":{\"strategy\":{\"type\":\"RollingUpdate\",\"rollingUpdate\":{\"maxSurge\":\"$RESTORE_MAX_SURGE\",\"maxUnavailable\":\"$RESTORE_MAX_UNAVAILABLE\"}}}}" >/dev/null
      else
        kubectl patch deployment/"$DEPLOYMENT" -n "$NAMESPACE" --type merge -p \
          "{\"spec\":{\"strategy\":{\"type\":\"$RESTORE_STRATEGY_TYPE\"}}}" >/dev/null
      fi
    fi
    ;;
  *)
    usage
    exit 1
    ;;
esac
