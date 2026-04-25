#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPERIMENT="$ROOT/experiments/native_bad_image_productcatalogservice_live_demo.yaml"

need_bin() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required binary: $1" >&2
    exit 1
  fi
}

need_bin python3
need_bin kubectl

if [ ! -f "$EXPERIMENT" ]; then
  echo "Experiment file not found: $EXPERIMENT" >&2
  exit 1
fi

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "Missing ANTHROPIC_API_KEY in the environment." >&2
  echo "Load your Anthropic credentials, then rerun the demo." >&2
  exit 1
fi

echo "[demo] Running native live remediation demo against productcatalogservice"
echo "[demo] Fault type is a native bad-image rollout"
echo "[demo] Agent type is react using Claude (claude-sonnet-4-0) with dry_run=false"
echo "[demo] Using --warm-cluster by default; pass --with-startup to boot/reset the stack first"

EXTRA_ARGS=()
if [ "${1:-}" = "--with-startup" ]; then
  shift
else
  EXTRA_ARGS+=(--warm-cluster)
fi

cd "$ROOT"
exec python3 ./scripts/run_experiment.py "$EXPERIMENT" "${EXTRA_ARGS[@]}" "$@"
