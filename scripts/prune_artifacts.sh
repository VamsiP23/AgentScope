#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

KEEP_RUNS=(
  "20260401T202355Z_bad_rollout_productcatalogservice_react"
  "20260403T121847Z_chaos_cpu_stress_checkoutservice_react_evidence"
)

echo "[prune] removing caches and local runtime state"
find . -type d -name "__pycache__" -prune -exec rm -rf {} +
find . -name ".DS_Store" -delete
rm -rf .runtime baseline_runs traffic_runs

echo "[prune] pruning experiment_runs (keeping ${#KEEP_RUNS[@]} run directories)"
if [[ -d experiment_runs ]]; then
  find experiment_runs -mindepth 1 -maxdepth 1 -type d | while read -r run_dir; do
    base="$(basename "$run_dir")"
    keep=false
    for wanted in "${KEEP_RUNS[@]}"; do
      if [[ "$base" == "$wanted" ]]; then
        keep=true
        break
      fi
    done
    if [[ "$keep" == false ]]; then
      rm -rf "$run_dir"
    fi
  done
fi

echo "[prune] done"
