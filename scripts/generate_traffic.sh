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
  -r   Requests per second (default: 4)
  -o   Output root directory (default: traffic_runs)
  -m   Traffic mode: realistic (default: realistic)
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
  *)
    echo "Mode must be realistic." >&2
    exit 1
    ;;
esac

TS_UTC=$(date -u +"%Y%m%dT%H%M%SZ")
OUT_DIR="$OUT_ROOT/$TS_UTC"
mkdir -p "$OUT_DIR"

REQUESTS_CSV="$OUT_DIR/requests.csv"
SUMMARY_TXT="$OUT_DIR/summary.txt"
COOKIE_JAR="$OUT_DIR/cookies.txt"

cat > "$REQUESTS_CSV" <<CSV
timestamp_utc,path,status_code,latency_ms
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
  }
  ' "$REQUESTS_CSV" > "$SUMMARY_TXT"
  cat >> "$SUMMARY_TXT" <<EOF
checkout_workflows=${checkout_count}
browse_only_workflows=${browse_only_count}
browse_cart_workflows=${browse_cart_count}
full_checkout_workflows=${full_checkout_count}
EOF
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

end_epoch=$(( $(date +%s) + DURATION ))
request_count=0
success_count=0
failure_count=0
checkout_count=0
browse_only_count=0
browse_cart_count=0
full_checkout_count=0

request_once() {
  local method="$1"
  local path="$2"
  local data="${3:-}"
  local now_ts code time_total latency_ms curl_out
  local curl_args=()

  now_ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  curl_args=(-s -L -o /dev/null -w "%{http_code} %{time_total}" -c "$COOKIE_JAR" -b "$COOKIE_JAR")
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
  echo "$now_ts,$method $path,$code,$latency_ms" >> "$REQUESTS_CSV"

  request_count=$((request_count + 1))
  if [ "$code" -ge 200 ] && [ "$code" -lt 500 ]; then
    success_count=$((success_count + 1))
  else
    failure_count=$((failure_count + 1))
  fi

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
  local product_path
  product_path="$(pick_product_path)"
  if [ -n "$product_path" ]; then
    request_once "GET" "$product_path"
  fi
}

browse_workflow() {
  local detail_views count
  browse_only_count=$((browse_only_count + 1))
  request_once "GET" "/"
  count=$((1 + RANDOM % 3))
  for ((detail_views=0; detail_views<count; detail_views++)); do
    browse_product_detail
  done
}

cart_workflow() {
  local product_path product_id quantity items_to_add i
  browse_cart_count=$((browse_cart_count + 1))
  if [ "${#PRODUCT_PATHS[@]}" -eq 0 ]; then
    browse_workflow
    return 0
  fi

  request_once "GET" "/"
  items_to_add=$((1 + RANDOM % 2))
  for ((i=0; i<items_to_add; i++)); do
    product_path="$(pick_product_path)"
    product_id="${product_path##*/}"
    quantity="$(random_quantity)"
    request_once "GET" "$product_path"
    request_once "POST" "/cart" "product_id=$product_id&quantity=$quantity"
  done
  request_once "GET" "/cart"
}

checkout_workflow() {
  local product_path product_id quantity items_to_add i
  full_checkout_count=$((full_checkout_count + 1))
  checkout_count=$((checkout_count + 1))
  if [ "${#PRODUCT_PATHS[@]}" -eq 0 ]; then
    browse_workflow
    return 0
  fi

  request_once "GET" "/"
  items_to_add=$((1 + RANDOM % 3))
  for ((i=0; i<items_to_add; i++)); do
    product_path="$(pick_product_path)"
    product_id="${product_path##*/}"
    quantity="$(random_quantity)"
    request_once "GET" "$product_path"
    request_once "POST" "/cart" "product_id=$product_id&quantity=$quantity"
  done
  request_once "GET" "/cart"
  request_once \
    "POST" \
    "/cart/checkout" \
    "email=someone%40example.com&street_address=1600+Amphitheatre+Parkway&zip_code=94043&city=Mountain+View&state=CA&country=United+States&credit_card_number=4432801561520454&credit_card_expiration_month=1&credit_card_expiration_year=2039&credit_card_cvv=672"
}

run_realistic_workflow() {
  local roll=$((RANDOM % 100))
  if [ "$roll" -lt 55 ]; then
    browse_workflow
  elif [ "$roll" -lt 80 ]; then
    cart_workflow
  else
    checkout_workflow
  fi
}

echo "Output directory: $OUT_DIR"
echo "Base URL: $BASE_URL"
echo "Duration: ${DURATION}s | Target RPS: $RPS | Mode: $MODE"
echo "Discovered product paths: ${PRODUCT_PATHS[*]}"
echo "Workflow weights: browse-only=55% browse+cart=25% full-checkout=20%"

while [ "$(date +%s)" -lt "$end_epoch" ]; do
  second_start=$(date +%s)

  for ((i=0; i<RPS; i++)); do
    run_realistic_workflow
  done

  now=$(date +%s)
  elapsed=$((now - second_start))
  if [ "$elapsed" -lt 1 ]; then
    sleep 1
  fi

  seconds_done=$(( $(date +%s) - (end_epoch - DURATION) ))
  if [ "$seconds_done" -gt 0 ] && [ $((seconds_done % PROGRESS_EVERY)) -eq 0 ]; then
    echo "Progress: ${seconds_done}s/${DURATION}s, requests=${request_count}, failures=${failure_count}"
  fi
done

write_summary

cat <<DONE

Traffic generation complete.
Requests CSV: $REQUESTS_CSV
Summary:      $SUMMARY_TXT
Requests:     $request_count (success=${success_count}, failures=${failure_count})
Checkouts:    $checkout_count
Workflows:    browse_only=${browse_only_count}, browse_cart=${browse_cart_count}, full_checkout=${full_checkout_count}
DONE
