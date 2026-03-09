#!/usr/bin/env bash
set -euo pipefail

RUNTIME_ROOT=".runtime"
RUN_DIR=""

usage() {
  cat <<USAGE
Stop background processes started by scripts/start_all.sh.

Usage:
  $(basename "$0") [-r run_dir]

Options:
  -r <run_dir>   Specific runtime directory (default: latest .runtime/start_all_*)
  -h             Show help

Examples:
  ./scripts/stop_all.sh
  ./scripts/stop_all.sh -r .runtime/start_all_20260309T120000Z
USAGE
}

while getopts ":r:h" opt; do
  case "$opt" in
    r) RUN_DIR="$OPTARG" ;;
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

if [ -z "$RUN_DIR" ]; then
  if [ ! -d "$RUNTIME_ROOT" ]; then
    echo "No runtime directory found at $RUNTIME_ROOT" >&2
    exit 1
  fi

  RUN_DIR=$(ls -dt "$RUNTIME_ROOT"/start_all_* 2>/dev/null | head -n 1 || true)
  if [ -z "$RUN_DIR" ]; then
    echo "No start_all runtime directories found under $RUNTIME_ROOT" >&2
    exit 1
  fi
fi

if [ ! -d "$RUN_DIR" ]; then
  echo "Run directory not found: $RUN_DIR" >&2
  exit 1
fi

echo "Stopping processes from: $RUN_DIR"

stop_by_pid_file() {
  local name="$1"
  local pid_file="$2"

  if [ ! -f "$pid_file" ]; then
    echo "  skip $name (pid file not found)"
    return
  fi

  local pid
  pid=$(cat "$pid_file")

  if [ -z "$pid" ]; then
    echo "  skip $name (empty pid file)"
    return
  fi

  if kill -0 "$pid" >/dev/null 2>&1; then
    kill "$pid" >/dev/null 2>&1 || true
    sleep 1
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill -9 "$pid" >/dev/null 2>&1 || true
    fi
    echo "  stopped $name (pid $pid)"
  else
    echo "  skip $name (pid $pid not running)"
  fi
}

stop_by_pid_file "frontend port-forward" "$RUN_DIR/frontend.pid"
stop_by_pid_file "jaeger port-forward" "$RUN_DIR/jaeger.pid"
stop_by_pid_file "prometheus port-forward" "$RUN_DIR/prometheus.pid"
stop_by_pid_file "grafana port-forward" "$RUN_DIR/grafana.pid"
stop_by_pid_file "traffic generator" "$RUN_DIR/traffic.pid"
stop_by_pid_file "baseline collector" "$RUN_DIR/baseline.pid"

echo "Done."
