# AgentScope Handoff

This document is the shortest honest path to keep the project moving without
pretending every experiment is benchmark-ready.

## Current status

The repository is in a much better state than it was during the earlier
debugging spiral:

- `start_all.sh` now tries to reuse healthy `Chaos Mesh` and observability
  infrastructure instead of reinstalling it every run.
- `reset_cluster.sh` is app-oriented by default and does not refresh the
  observability stack unless explicitly asked.
- telemetry validation exists in `scripts/validate_telemetry.py`
- evidence probing exists in `scripts/run_evidence_probe.py`
- the ACI and ReAct agent path are wired end to end
- `get_logs` resolution is more reliable than before
- Jaeger failures are classified as observability failures instead of service
  failures

What is still not fully solved:

- resource usage metrics are still incomplete in `get_metrics(...)`
  for CPU-stress reasoning
- checkout dependency localization via `get_dependency_traces(...)` is still
  weak in some windows
- startup is still slower than it should be because stable-local deployment
  settings are applied via runtime patching rather than a persistent local
  overlay

## Recommended reduced scope

If the goal is to hand off a stable, defensible benchmark slice, do not block on
every candidate experiment.

### Keep as core

1. `bad_rollout_productcatalogservice`
   - strongest, clearest control case
   - evidence is mostly K8s state + logs
   - does not depend on perfect resource telemetry

### Keep as secondary / likely usable

1. `bad_rollout_recommendationservice`
   - same failure class as productcatalog
   - useful for showing the agent is not memorizing one service

### Keep as candidate only

1. `cpu_stress_checkoutservice`
   - detector and evidence are much better than before
   - telemetry still lacks live CPU/memory usage in `get_metrics`
   - use as a calibration case, not as a core benchmark claim

2. `cpu_stress_frontend`
   - probably easier than checkout in the long term because all traffic hits
     `frontend`
   - not yet validated enough to promote

3. `network_delay_frontend_productcatalogservice`
4. `network_delay_frontend_currencyservice`
   - promising trace-localization cases
   - keep as candidates until repeated evidence runs are clean

## Recommended handoff story

The best handoff message is:

"The environment and benchmark harness are working end to end. The rollout
faults are the cleanest benchmark slice today. The resource/dependency cases are
partially working, and telemetry validation + evidence probing were added so the
next person can improve those cases without guessing."

That is honest and technically strong.

## Known-good workflow

### 1. Bootstrap once per session

```bash
./scripts/start_all.sh -c docker-desktop
```

Notes:

- startup is still slower than ideal
- if it fails, check `cartservice` first before blaming observability
- healthy infra is reused now; the script should not reinstall everything every run

### 2. Validate telemetry before blaming the agent

```bash
python3 ./scripts/validate_telemetry.py \
  --prom-url http://localhost:9090 \
  --jaeger-url http://localhost:16686 \
  --namespace default
```

Expected:

- `ok: true`
- Prometheus scrape targets up
- Jaeger services visible

### 3. Probe evidence before running the agent on a candidate fault

```bash
python3 ./scripts/run_evidence_probe.py \
  experiments/chaos_cpu_stress_checkoutservice_react.yaml \
  --skip-startup \
  --include-dependencies \
  --lookback-minutes 1
```

Use the resulting `evidence_report.json` to decide whether the fault is ready
for agent evaluation.

### 4. Run an experiment

```bash
python3 ./scripts/run_experiment.py \
  experiments/bad_rollout_productcatalogservice_react.yaml \
  --skip-startup
```

For checkout CPU stress, prefer validating telemetry and evidence first.

## What the latest evidence run showed

From `experiment_runs/20260402T215234Z_chaos_cpu_stress_checkoutservice_react_evidence/`:

- detector fired cleanly
- `checkoutservice` latency was strongly elevated
- K8s state and logs were rich
- traces for `checkoutservice` and `frontend` were rich
- `get_metrics(checkoutservice)` was still only `weak`
- downstream service metrics were still `missing`

Interpretation:

- the telemetry stack is no longer fundamentally broken
- the remaining evidence gap is concentrated in resource usage metrics
- this is why CPU-stress reasoning is still less reliable than rollout reasoning

## Files to know first

### Core execution

- `scripts/start_all.sh`
- `scripts/reset_cluster.sh`
- `scripts/run_experiment.py`
- `scripts/run_react_agent.py`

### Telemetry validation / debugging

- `scripts/validate_telemetry.py`
- `scripts/run_evidence_probe.py`
- `observability/manifests/prometheus.yaml`
- `observability/manifests/jaeger.yaml`
- `observability/manifests/otel-collector.yaml`
- `observability/manifests/kube-state-metrics.yaml`

### Agent / ACI

- `agent_graph/aci.py`
- `agent_graph/react_agent.py`
- `agent_graph/tools/prometheus.py`
- `agent_graph/tools/jaeger.py`
- `agent_graph/tools/kubernetes.py`

### Benchmark configuration

- `benchmark_suite.yaml`
- `experiments/*.yaml`

## Open problems left for the next person

### 1. Replace runtime stable-local patching with a persistent local overlay

Current startup is still slow because it patches many deployments and forces
rollouts. The right fix is to move those settings into a dedicated local manifest
or overlay and stop patching them every session.

### 2. Fix live resource usage collection in `get_metrics`

Requests/limits are present, but live resource usage is still coming back as
`null` in many cases:

- `cpu_usage`
- `cpu_throttled_seconds_rate`
- `memory_usage`

This is the main blocker for trustworthy CPU-stress diagnosis.

### 3. Improve dependency trace localization for checkout

`get_dependency_traces(checkoutservice, entry_service="frontend")` still often
returns weak evidence even when plain traces are available.

## What not to do

- do not claim all experiments are benchmark-ready
- do not reintroduce per-run observability reinstall/restart churn
- do not treat trace retrieval failure as service failure
- do not spend more time on cart/redis as a core benchmark path unless telemetry
  coverage is intentionally expanded there

## Suggested immediate next milestone

If continuing the project, the highest-value next milestone is:

"Make the rollout benchmark slice clean and repeatable, and make CPU-stress
resource metrics trustworthy enough that checkout or frontend CPU stress can be
promoted from candidate to ready."

That is a much better use of time than trying to make every experiment perfect
at once.
