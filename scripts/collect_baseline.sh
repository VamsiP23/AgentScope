#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="default"
INTERVAL=15
DURATION=300
OUT_ROOT="baseline_runs"
LABEL_SELECTOR=""

usage() {
  cat <<USAGE
Collect baseline Kubernetes observability snapshots for Online Boutique.

Usage:
  $(basename "$0") [-n namespace] [-i interval_seconds] [-d duration_seconds] [-o output_root] [-l label_selector]

Options:
  -n   Kubernetes namespace (default: default)
  -i   Sampling interval in seconds (default: 15)
  -d   Total duration in seconds (default: 300)
  -o   Output root directory (default: baseline_runs)
  -l   Optional label selector (example: app=cartservice)
  -h   Show this help
USAGE
}

while getopts ":n:i:d:o:l:h" opt; do
  case "$opt" in
    n) NAMESPACE="$OPTARG" ;;
    i) INTERVAL="$OPTARG" ;;
    d) DURATION="$OPTARG" ;;
    o) OUT_ROOT="$OPTARG" ;;
    l) LABEL_SELECTOR="$OPTARG" ;;
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

if ! [[ "$INTERVAL" =~ ^[0-9]+$ ]] || ! [[ "$DURATION" =~ ^[0-9]+$ ]]; then
  echo "Interval and duration must be positive integers." >&2
  exit 1
fi

if [ "$INTERVAL" -le 0 ] || [ "$DURATION" -le 0 ]; then
  echo "Interval and duration must be greater than zero." >&2
  exit 1
fi

SAMPLE_COUNT=$((DURATION / INTERVAL))
if [ "$SAMPLE_COUNT" -lt 1 ]; then
  SAMPLE_COUNT=1
fi

TS_UTC=$(date -u +"%Y%m%dT%H%M%SZ")
OUT_DIR="$OUT_ROOT/$TS_UTC"
mkdir -p "$OUT_DIR"

K_ARGS=( -n "$NAMESPACE" )
if [ -n "$LABEL_SELECTOR" ]; then
  K_ARGS+=( -l "$LABEL_SELECTOR" )
fi

SUMMARY_CSV="$OUT_DIR/summary.csv"
cat > "$SUMMARY_CSV" <<CSV
sample,timestamp_utc,total_pods,running,pending,failed,unknown,total_restarts
CSV

log_cmd() {
  local output_file="$1"
  shift
  {
    echo "# command: $*"
    "$@"
  } >"$output_file" 2>&1 || true
}

safe_top() {
  local output_file="$1"
  shift
  {
    echo "# command: $*"
    if "$@"; then
      :
    else
      echo "metrics-server unavailable or top command failed"
    fi
  } >"$output_file" 2>&1 || true
}

echo "Output directory: $OUT_DIR"
echo "Namespace: $NAMESPACE"
[ -n "$LABEL_SELECTOR" ] && echo "Label selector: $LABEL_SELECTOR"
echo "Duration: ${DURATION}s | Interval: ${INTERVAL}s | Samples: ${SAMPLE_COUNT}"

log_cmd "$OUT_DIR/cluster_info.txt" kubectl cluster-info
log_cmd "$OUT_DIR/nodes.txt" kubectl get nodes -o wide
log_cmd "$OUT_DIR/deployments.txt" kubectl get deployments "${K_ARGS[@]}" -o wide
log_cmd "$OUT_DIR/services.txt" kubectl get services "${K_ARGS[@]}" -o wide
log_cmd "$OUT_DIR/pods_initial.txt" kubectl get pods "${K_ARGS[@]}" -o wide
safe_top "$OUT_DIR/top_nodes_initial.txt" kubectl top nodes
safe_top "$OUT_DIR/top_pods_initial.txt" kubectl top pods "${K_ARGS[@]}"

for ((i=1; i<=SAMPLE_COUNT; i++)); do
  SAMPLE_TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  PREFIX=$(printf "sample_%03d" "$i")

  POD_TABLE=$(kubectl get pods "${K_ARGS[@]}" --no-headers 2>/dev/null || true)

  TOTAL_PODS=$(printf "%s\n" "$POD_TABLE" | awk 'NF>0 {c++} END {print c+0}')
  RUNNING=$(printf "%s\n" "$POD_TABLE" | awk '$3=="Running" {c++} END {print c+0}')
  PENDING=$(printf "%s\n" "$POD_TABLE" | awk '$3=="Pending" {c++} END {print c+0}')
  FAILED=$(printf "%s\n" "$POD_TABLE" | awk '$3=="Failed" {c++} END {print c+0}')
  UNKNOWN=$(printf "%s\n" "$POD_TABLE" | awk '$3=="Unknown" {c++} END {print c+0}')
  RESTARTS=$(printf "%s\n" "$POD_TABLE" | awk 'NF>0 {sum+=$4} END {print sum+0}')

  printf "%s,%s,%s,%s,%s,%s,%s,%s\n" \
    "$i" "$SAMPLE_TS" "$TOTAL_PODS" "$RUNNING" "$PENDING" "$FAILED" "$UNKNOWN" "$RESTARTS" >> "$SUMMARY_CSV"

  log_cmd "$OUT_DIR/${PREFIX}_pods.txt" kubectl get pods "${K_ARGS[@]}" -o wide
  safe_top "$OUT_DIR/${PREFIX}_top_pods.txt" kubectl top pods "${K_ARGS[@]}"
  log_cmd "$OUT_DIR/${PREFIX}_events.txt" kubectl get events "${K_ARGS[@]}" --sort-by=.metadata.creationTimestamp

  echo "[$SAMPLE_TS] sample $i/$SAMPLE_COUNT collected"

  if [ "$i" -lt "$SAMPLE_COUNT" ]; then
    sleep "$INTERVAL"
  fi
done

log_cmd "$OUT_DIR/pods_final.txt" kubectl get pods "${K_ARGS[@]}" -o wide
safe_top "$OUT_DIR/top_pods_final.txt" kubectl top pods "${K_ARGS[@]}"

echo ""
echo "Baseline collection complete."
echo "Summary CSV: $SUMMARY_CSV"
