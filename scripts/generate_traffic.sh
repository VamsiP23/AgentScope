#!/usr/bin/env bash
set -uo pipefail

BASE_URL="http://localhost:8080"
DURATION=300
RPS=4
OUT_ROOT="traffic_runs"
PROGRESS_EVERY=10
MODE="realistic"

usage() {
  cat <<USAGE
Generate synthetic HTTP traffic against Online Boutique frontend.

Usage:
  $(basename "$0") [-u base_url] [-d duration_seconds] [-r requests_per_second] [-o output_root] [-m mode]

Options:
  -u   Base URL for frontend (default: http://localhost:8080)
  -d   Total duration in seconds (default: 300)
  -r   Workflow starts per second (default: 4)
  -o   Output root directory (default: traffic_runs)
  -m   Traffic mode: realistic | checkout-heavy | browse-heavy (default: realistic)
  -h   Show this help
USAGE
}

while getopts ":u:d:r:o:m:h" opt; do
  case "$opt" in
    u) BASE_URL="$OPTARG" ;;
    d) DURATION="$OPTARG" ;;
    r) RPS="$OPTARG" ;;
    o) OUT_ROOT="$OPTARG" ;;
    m) MODE="$OPTARG" ;;
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

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required but not installed." >&2
  exit 1
fi

if ! [[ "$DURATION" =~ ^[0-9]+$ ]] || ! [[ "$RPS" =~ ^[0-9]+$ ]]; then
  echo "Duration and RPS must be positive integers." >&2
  exit 1
fi

if [ "$DURATION" -le 0 ] || [ "$RPS" -le 0 ]; then
  echo "Duration and RPS must be greater than zero." >&2
  exit 1
fi

case "$MODE" in
  realistic|basic|full-flow) MODE="realistic" ;;
  checkout-heavy|checkout|cpu-stress) MODE="checkout-heavy" ;;
  browse-heavy|browse) MODE="browse-heavy" ;;
  *)
    echo "Mode must be one of: realistic, checkout-heavy, browse-heavy." >&2
    exit 1
    ;;
esac

TS_UTC=$(date -u +"%Y%m%dT%H%M%SZ")
OUT_DIR="$OUT_ROOT/$TS_UTC"
mkdir -p "$OUT_DIR"

REQUESTS_CSV="$OUT_DIR/requests.csv"
WORKFLOWS_CSV="$OUT_DIR/workflows.csv"
SUMMARY_TXT="$OUT_DIR/summary.txt"
BATCH_ROOT="$OUT_DIR/batches"
mkdir -p "$BATCH_ROOT"

cat > "$REQUESTS_CSV" <<CSV
timestamp_utc,path,status_code,latency_ms
CSV

cat > "$WORKFLOWS_CSV" <<CSV
timestamp_utc,workflow_type
CSV

write_summary() {
  awk -F, '
  NR>1 {
    code=$3+0;
    lat[NR-1]=$4+0;
    n++;
    if (code >= 500 || code == 0) err5xx++;
  }
  END {
    if (n == 0) {
      print "total_requests=0";
      print "avg_latency_ms=0";
      print "p95_latency_ms=0";
      print "server_error_requests=0";
      print "request_failures=0";
      exit;
    }

    for (i=1; i<=n; i++) sum += lat[i];
    avg = sum / n;

    # insertion sort; n is typically small for baseline runs
    for (i=2; i<=n; i++) {
      key = lat[i];
      j = i-1;
      while (j >= 1 && lat[j] > key) {
        lat[j+1] = lat[j];
        j--;
      }
      lat[j+1] = key;
    }

    p95_idx = int((0.95*n)+0.999999);
    if (p95_idx < 1) p95_idx = 1;
    if (p95_idx > n) p95_idx = n;

    printf "total_requests=%d\n", n;
    printf "avg_latency_ms=%.2f\n", avg;
    printf "p95_latency_ms=%.2f\n", lat[p95_idx];
    printf "server_error_requests=%d\n", err5xx+0;
    printf "request_failures=%d\n", err5xx+0;
  }
  ' "$REQUESTS_CSV" > "$SUMMARY_TXT"
  awk -F, '
  NR>1 {
    counts[$2]++;
    total++;
  }
  END {
    printf "total_workflows=%d\n", total+0;
    printf "browse_only_workflows=%d\n", counts["browse_only"]+0;
    printf "browse_cart_workflows=%d\n", counts["browse_cart"]+0;
    printf "full_checkout_workflows=%d\n", counts["full_checkout"]+0;
  }
  ' "$WORKFLOWS_CSV" >> "$SUMMARY_TXT"
}

on_exit() {
  write_summary || true
}

trap on_exit EXIT

normalize_base_url() {
  local url="$1"
  echo "${url%/}"
}

BASE_URL=$(normalize_base_url "$BASE_URL")

PRODUCT_PATHS=()
while IFS= read -r line; do
  [ -n "$line" ] && PRODUCT_PATHS+=("$line")
done < <(
  curl -fsSL "$BASE_URL" 2>/dev/null \
  | grep -oE '/product/[A-Za-z0-9._-]+' \
  | sort -u || true
)

request_once() {
  local request_csv="$1"
  local cookie_jar="$2"
  local method="$3"
  local path="$4"
  local data="${5:-}"
  local now_ts code time_total latency_ms curl_out
  local curl_args=()

  now_ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  curl_args=(-s -L -o /dev/null -w "%{http_code} %{time_total}" -c "$cookie_jar" -b "$cookie_jar")
  if [ "$method" = "POST" ]; then
    curl_args+=(-X POST)
    if [ -n "$data" ]; then
      curl_args+=(--data "$data")
    fi
  fi
  curl_out=$(curl "${curl_args[@]}" "$BASE_URL$path" 2>/dev/null || true)
  if [ -z "$curl_out" ]; then
    code="000"
    time_total="0"
  else
    code="${curl_out%% *}"
    time_total="${curl_out#* }"
    if [ -z "$code" ] || [ -z "$time_total" ]; then
      code="000"
      time_total="0"
    fi
  fi

  latency_ms=$(awk -v t="$time_total" 'BEGIN {printf "%.2f", t*1000}')
  echo "$now_ts,$method $path,$code,$latency_ms" >> "$request_csv"

  return 0
}

random_quantity() {
  local options=(1 2 3 4 5)
  echo "${options[$((RANDOM % ${#options[@]}))]}"
}

pick_product_path() {
  if [ "${#PRODUCT_PATHS[@]}" -eq 0 ]; then
    echo ""
    return 0
  fi
  echo "${PRODUCT_PATHS[$((RANDOM % ${#PRODUCT_PATHS[@]}))]}"
}

browse_product_detail() {
  local request_csv="$1"
  local cookie_jar="$2"
  local product_path
  product_path="$(pick_product_path)"
  if [ -n "$product_path" ]; then
    request_once "$request_csv" "$cookie_jar" "GET" "$product_path"
  fi
}

browse_workflow() {
  local request_csv="$1"
  local cookie_jar="$2"
  local detail_views count
  request_once "$request_csv" "$cookie_jar" "GET" "/"
  count=$((1 + RANDOM % 3))
  for ((detail_views=0; detail_views<count; detail_views++)); do
    browse_product_detail "$request_csv" "$cookie_jar"
  done
}

cart_workflow() {
  local request_csv="$1"
  local cookie_jar="$2"
  local product_path product_id quantity items_to_add i
  if [ "${#PRODUCT_PATHS[@]}" -eq 0 ]; then
    browse_workflow "$request_csv" "$cookie_jar"
    return 0
  fi

  request_once "$request_csv" "$cookie_jar" "GET" "/"
  items_to_add=$((1 + RANDOM % 2))
  for ((i=0; i<items_to_add; i++)); do
    product_path="$(pick_product_path)"
    product_id="${product_path##*/}"
    quantity="$(random_quantity)"
    request_once "$request_csv" "$cookie_jar" "GET" "$product_path"
    request_once "$request_csv" "$cookie_jar" "POST" "/cart" "product_id=$product_id&quantity=$quantity"
  done
  request_once "$request_csv" "$cookie_jar" "GET" "/cart"
}

checkout_workflow() {
  local request_csv="$1"
  local cookie_jar="$2"
  local minimal="${3:-0}"
  local product_path product_id quantity items_to_add i
  if [ "${#PRODUCT_PATHS[@]}" -eq 0 ]; then
    browse_workflow "$request_csv" "$cookie_jar"
    return 0
  fi

  request_once "$request_csv" "$cookie_jar" "GET" "/"
  if [ "$minimal" -eq 1 ]; then
    items_to_add=1
  else
    items_to_add=$((1 + RANDOM % 3))
  fi
  for ((i=0; i<items_to_add; i++)); do
    product_path="$(pick_product_path)"
    product_id="${product_path##*/}"
    quantity="$(random_quantity)"
    request_once "$request_csv" "$cookie_jar" "GET" "$product_path"
    request_once "$request_csv" "$cookie_jar" "POST" "/cart" "product_id=$product_id&quantity=$quantity"
  done
  request_once "$request_csv" "$cookie_jar" "GET" "/cart"
  request_once "$request_csv" "$cookie_jar" \
    "POST" \
    "/cart/checkout" \
    "email=someone%40example.com&street_address=1600+Amphitheatre+Parkway&zip_code=94043&city=Mountain+View&state=CA&country=United+States&credit_card_number=4432801561520454&credit_card_expiration_month=1&credit_card_expiration_year=2039&credit_card_cvv=672"
}

direct_checkout_workflow() {
  local request_csv="$1"
  local cookie_jar="$2"
  local product_path product_id quantity
  if [ "${#PRODUCT_PATHS[@]}" -eq 0 ]; then
    browse_workflow "$request_csv" "$cookie_jar"
    return 0
  fi

  product_path="$(pick_product_path)"
  product_id="${product_path##*/}"
  quantity="$(random_quantity)"
  request_once "$request_csv" "$cookie_jar" "POST" "/cart" "product_id=$product_id&quantity=$quantity"
  request_once "$request_csv" "$cookie_jar" "GET" "/cart"
  request_once "$request_csv" "$cookie_jar" \
    "POST" \
    "/cart/checkout" \
    "email=someone%40example.com&street_address=1600+Amphitheatre+Parkway&zip_code=94043&city=Mountain+View&state=CA&country=United+States&credit_card_number=4432801561520454&credit_card_expiration_month=1&credit_card_expiration_year=2039&credit_card_cvv=672"
}

run_workflow_for_mode() {
  local request_csv="$1"
  local cookie_jar="$2"
  local roll=$((RANDOM % 100))
  case "$MODE" in
    checkout-heavy)
      if [ "$roll" -lt 5 ]; then
        browse_workflow "$request_csv" "$cookie_jar"
        echo "browse_only"
      elif [ "$roll" -lt 10 ]; then
        cart_workflow "$request_csv" "$cookie_jar"
        echo "browse_cart"
      else
        direct_checkout_workflow "$request_csv" "$cookie_jar"
        echo "full_checkout"
      fi
      ;;
    browse-heavy)
      if [ "$roll" -lt 80 ]; then
        browse_workflow "$request_csv" "$cookie_jar"
        echo "browse_only"
      elif [ "$roll" -lt 95 ]; then
        cart_workflow "$request_csv" "$cookie_jar"
        echo "browse_cart"
      else
        checkout_workflow "$request_csv" "$cookie_jar" 0
        echo "full_checkout"
      fi
      ;;
    *)
      if [ "$roll" -lt 55 ]; then
        browse_workflow "$request_csv" "$cookie_jar"
        echo "browse_only"
      elif [ "$roll" -lt 80 ]; then
        cart_workflow "$request_csv" "$cookie_jar"
        echo "browse_cart"
      else
        checkout_workflow "$request_csv" "$cookie_jar" 0
        echo "full_checkout"
      fi
      ;;
  esac
}

run_single_workflow() {
  local batch_dir="$1"
  local index="$2"
  local request_csv="$batch_dir/workflow_${index}.csv"
  local workflow_meta="$batch_dir/workflow_${index}.meta"
  local cookie_jar="$batch_dir/workflow_${index}.cookies.txt"
  local workflow_type

  : > "$request_csv"
  workflow_type="$(run_workflow_for_mode "$request_csv" "$cookie_jar")"
  printf "%s,%s\n" "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$workflow_type" > "$workflow_meta"
  rm -f "$cookie_jar"
}

append_batch_results() {
  local batch_dir="$1"
  local file
  for file in "$batch_dir"/workflow_*.csv; do
    [ -f "$file" ] || continue
    cat "$file" >> "$REQUESTS_CSV"
  done
  for file in "$batch_dir"/workflow_*.meta; do
    [ -f "$file" ] || continue
    cat "$file" >> "$WORKFLOWS_CSV"
  done
}

metric_value() {
  local key="$1"
  awk -F= -v target="$key" '$1 == target {print $2}' "$SUMMARY_TXT" 2>/dev/null | tail -n 1
}

echo "Output directory: $OUT_DIR"
echo "Base URL: $BASE_URL"
echo "Duration: ${DURATION}s | Target RPS: $RPS | Mode: $MODE"
if [ "${#PRODUCT_PATHS[@]}" -eq 0 ]; then
  echo "Discovered product paths: none"
else
  echo "Discovered product paths: ${PRODUCT_PATHS[*]}"
fi
case "$MODE" in
  checkout-heavy) echo "Workflow weights: browse-only=5% browse+cart=5% full-checkout=90% (direct checkout path)" ;;
  browse-heavy) echo "Workflow weights: browse-only=80% browse+cart=15% full-checkout=5%" ;;
  *) echo "Workflow weights: browse-only=55% browse+cart=25% full-checkout=20%" ;;
esac

end_epoch=$(( $(date +%s) + DURATION ))
batch_index=0

while [ "$(date +%s)" -lt "$end_epoch" ]; do
  local_batch_dir="$BATCH_ROOT/batch_${batch_index}"
  mkdir -p "$local_batch_dir"
  second_start=$(date +%s)

  for ((i=0; i<RPS; i++)); do
    run_single_workflow "$local_batch_dir" "$i" &
  done
  wait
  append_batch_results "$local_batch_dir"
  rm -rf "$local_batch_dir"
  batch_index=$((batch_index + 1))

  now=$(date +%s)
  elapsed=$((now - second_start))
  if [ "$elapsed" -lt 1 ]; then
    sleep 1
  fi

  seconds_done=$(( $(date +%s) - (end_epoch - DURATION) ))
  if [ "$seconds_done" -gt 0 ] && [ $((seconds_done % PROGRESS_EVERY)) -eq 0 ]; then
    write_summary || true
    echo "Progress: ${seconds_done}s/${DURATION}s, requests=$(metric_value total_requests), failures=$(metric_value request_failures)"
  fi
done

write_summary

cat <<DONE

Traffic generation complete.
Requests CSV: $REQUESTS_CSV
Workflows CSV: $WORKFLOWS_CSV
Summary:      $SUMMARY_TXT
Requests:     $(metric_value total_requests) (failures=$(metric_value request_failures))
Workflows:    total=$(metric_value total_workflows), browse_only=$(metric_value browse_only_workflows), browse_cart=$(metric_value browse_cart_workflows), full_checkout=$(metric_value full_checkout_workflows)
DONE
