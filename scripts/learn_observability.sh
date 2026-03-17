#!/usr/bin/env bash
set -euo pipefail

PROM_URL="http://localhost:9090"
JAEGER_URL="http://localhost:16686"
WINDOW="1m"
SERVICE="frontend"
LOOKBACK="1h"

usage() {
  cat <<USAGE
Learn the current observability setup by printing trace anatomy and running
sample Prometheus queries against your local stack.

Usage:
  ./scripts/learn_observability.sh [options]

Options:
  -p <prom_url>     Prometheus base URL (default: http://localhost:9090)
  -j <jaeger_url>   Jaeger base URL (default: http://localhost:16686)
  -w <window>       PromQL rate window (default: 1m)
  -s <service>      Service name for Jaeger examples (default: frontend)
  -l <lookback>     Jaeger lookback hint to display (default: 1h)
  -h                Show help
USAGE
}

while getopts ":p:j:w:s:l:h" opt; do
  case "$opt" in
    p) PROM_URL="$OPTARG" ;;
    j) JAEGER_URL="$OPTARG" ;;
    w) WINDOW="$OPTARG" ;;
    s) SERVICE="$OPTARG" ;;
    l) LOOKBACK="$OPTARG" ;;
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

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required but not installed." >&2
  exit 1
fi

section() {
  printf '\n== %s ==\n' "$1"
}

prom_query() {
  local query="$1"
  curl -fsG "$PROM_URL/api/v1/query" --data-urlencode "query=$query"
}

show_prom_result() {
  local label="$1"
  local query="$2"

  echo "Query: $query"
  if ! payload="$(prom_query "$query" 2>/dev/null)"; then
    echo "Result: Prometheus query failed. Make sure $PROM_URL is reachable."
    return 1
  fi

  printf '%s' "$payload" | python3 - "$label" <<'PY'
import json
import sys
label = sys.argv[1]
payload = json.load(sys.stdin)
print(f"Result summary for {label}:")
results = payload.get("data", {}).get("result", [])
if not results:
    print("  no series returned")
    raise SystemExit(0)
for row in results[:8]:
    metric = row.get("metric", {})
    value = row.get("value", [None, ""])[1]
    if metric:
        parts = [f"{k}={v}" for k, v in sorted(metric.items())]
        print("  " + ", ".join(parts) + f" -> {value}")
    else:
        print(f"  scalar -> {value}")
if len(results) > 8:
    print(f"  ... {len(results) - 8} more series")
PY
}

section "What A Trace Contains"
cat <<EOF
A trace is one end-to-end request. It is made of spans.

Each span usually contains:
- trace_id: groups all spans for one request
- span_id: unique id for that operation
- parent_span_id: which span called it
- service.name: which service emitted it
- operation/span name: what work it represents
- start time and duration: when it ran and how long it took
- span kind: server, client, internal, producer, consumer
- attributes/tags: http.method, http.status_code, rpc.method, error data
- status: ok or error
- events: exceptions, retries, checkpoints

How to read a trace:
1. start at the root span, usually frontend
2. check total trace duration
3. inspect the waterfall for the longest or failed child span
4. identify whether the root service is the cause or just surfacing a downstream failure
EOF

section "Jaeger Checklist"
cat <<EOF
Open Jaeger: $JAEGER_URL
Suggested search:
- Service: $SERVICE
- Lookback: Last ${LOOKBACK}
- Open a trace with multiple spans

Look for:
- root span: user-facing request
- child spans: downstream service calls
- error tags: where failure starts
- longest bar in waterfall: likely bottleneck
EOF

section "Prometheus Query Basics"
cat <<EOF
Prometheus stores time series. A query usually answers one of these:
- what is the current value?
- what is the rate over time?
- grouped by which label?

Patterns to notice:
- rate(metric[${WINDOW}]): per-second change over a time window
- sum(...): aggregate across instances/spans
- by (service_name): group results by service
EOF

section "Live Prometheus Checks"
if curl -fsS "$PROM_URL/-/ready" >/dev/null 2>&1; then
  echo "Prometheus is reachable at $PROM_URL"
else
  echo "Prometheus is not reachable at $PROM_URL"
fi

show_prom_result "Traffic by service" "sum(rate(calls_total[$WINDOW])) by (service_name)" || true
printf '\n'
show_prom_result "Error rate by service" "sum(rate(calls_total{status_code=\"STATUS_CODE_ERROR\"}[$WINDOW])) by (service_name)" || true
printf '\n'
show_prom_result "Total request rate" "sum(rate(calls_total[$WINDOW]))" || true

section "How To Interpret The Results"
cat <<EOF
- Traffic by service:
  which services are active right now
- Error rate by service:
  which services are surfacing failures right now
- Total request rate:
  whether your generator is producing load

If a service outage is injected:
- traffic may drop for the target or downstream path
- frontend often shows the error because it surfaces user-facing failures
- traces in Jaeger should show which child span actually failed first
EOF

section "Good Next Queries To Try Manually"
cat <<EOF
In Prometheus UI ($PROM_URL), try:

sum(rate(calls_total[1m])) by (service_name)
sum(rate(calls_total{status_code=\"STATUS_CODE_ERROR\"}[1m])) by (service_name)
sum(rate(calls_total[1m]))

During a fault, re-run the same queries and compare:
- baseline
- during fault
- after recovery
EOF
