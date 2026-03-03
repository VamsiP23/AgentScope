#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="default"

while getopts ":n:h" opt; do
  case "$opt" in
    n) NAMESPACE="$OPTARG" ;;
    h)
      echo "Usage: $(basename "$0") [-n namespace]"
      exit 0
      ;;
    *)
      echo "Usage: $(basename "$0") [-n namespace]" >&2
      exit 1
      ;;
  esac
done

for manifest in observability/manifests/*.yaml; do
  kubectl delete -n "$NAMESPACE" -f "$manifest" --ignore-not-found
done

echo "Observability resources removed from namespace: $NAMESPACE"
