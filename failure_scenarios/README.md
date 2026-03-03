# Failure Injection Scenarios

This runbook is designed for the project goal in your checkpoint report:
- measure AI-agent incident response quality under controlled failures
- evaluate detection speed, root-cause accuracy, and time-to-recovery

Use this script:

```bash
./scripts/failure_inject.sh <apply|revert> <scenario> [options]
```

## Scenarios

### 1) `service_outage`
Simulates a hard outage by scaling a service deployment to zero replicas.

```bash
./scripts/failure_inject.sh apply service_outage -n default -t checkoutservice -d 120
```

Expected signals:
- frontend checkout requests fail
- `checkoutservice` pod count drops to 0
- error rate rises in traces/metrics

### 2) `dependency_outage`
Simulates cart backend dependency loss by scaling `redis-cart` to zero.

```bash
./scripts/failure_inject.sh apply dependency_outage -n default -d 120
```

Expected signals:
- add-to-cart failures
- cartservice errors and retries
- dependency-related error traces

### 3) `latency_spike`
Injects per-request delay into `productcatalogservice` via `EXTRA_LATENCY`.

```bash
./scripts/failure_inject.sh apply latency_spike -n default -l 5s -d 180
```

Expected signals:
- increased p95/p99 latency
- slower product page/API paths
- spans inflated around product catalog RPCs

### 4) `cpu_pressure`
Triggers product catalog CPU-heavy mode (`USR1`) and restores with `USR2`.

```bash
./scripts/failure_inject.sh apply cpu_pressure -n default -d 180
```

Expected signals:
- higher CPU usage for product catalog pod
- increased response times
- elevated processing delay in related traces

## How To Verify Slowdowns

Use `latency_spike` as the canonical slowdown test:

1. Terminal 1:
   ```bash
   kubectl port-forward -n default svc/frontend 8080:80
   ```
2. Terminal 2:
   ```bash
   ./scripts/generate_traffic.sh -u http://localhost:8080 -d 300 -r 4
   ```
3. After ~60s, Terminal 3:
   ```bash
   ./scripts/failure_inject.sh apply latency_spike -n default -l 5s -d 120
   ```

### A) Check traffic CSV directly

```bash
TRAF=$(ls -1dt traffic_runs/* | head -1)
cat "$TRAF/summary.txt"
awk -F, 'NR>1 {print $1,$2,$3,$4}' "$TRAF/requests.csv" | sed -n '1,40p'
```

What to look for:
- `avg_latency_ms` and `p95_latency_ms` rising
- request rows with larger `latency_ms`
- possible 5xx increase during the injection window

### B) Check Prometheus/Grafana latency

```promql
sum(rate(calls_total[1m])) by (service_name)
```

```promql
histogram_quantile(0.95, sum(rate(duration_bucket[1m])) by (le, service_name))
```

What to look for:
- p95 jump for `productcatalogservice`
- frontend latency increase due to downstream slowdown

### C) Check Jaeger traces

- Service: `frontend` (and optionally `productcatalogservice`)
- Lookback: last 15 minutes
- Min Duration: `500ms` or `1s`

What to look for:
- slower traces concentrated in the injection period
- longer spans around product catalog calls

## Suggested Evaluation Flow

1. Start frontend + observability stack.
2. Start baseline collector:
   ```bash
   ./scripts/collect_baseline.sh -n default -i 15 -d 600
   ```
3. Start synthetic traffic:
   ```bash
   ./scripts/generate_traffic.sh -u http://localhost:8080 -d 600 -r 4
   ```
4. Inject one scenario for 2-3 minutes.
5. Capture:
   - failure start timestamp (UTC)
   - first detection timestamp by agent/alerts
   - root-cause hypothesis produced by agent
   - recovery action and recovery timestamp

## Scoring Template

- `time_to_detect_sec = first_detection_ts - failure_start_ts`
- `time_to_recover_sec = recovered_ts - failure_start_ts`
- `root_cause_correct = true|false`
- `recovery_action_correct = true|false`

Store per-run artifacts in:
- `baseline_runs/<timestamp>/`
- `traffic_runs/<timestamp>/`
