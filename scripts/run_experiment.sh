#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: ./scripts/run_experiment.sh <experiment.yaml> [--out-dir <dir>]" >&2
  exit 1
fi

exec python3 ./scripts/run_experiment.py "$@"
