# Experiments

Each YAML file in this directory defines one reproducible AgentScope experiment.

Run one experiment with:

```bash
./scripts/run_experiment.sh experiments/service_outage_cartservice.yaml
```

Each run writes artifacts under `experiment_runs/<timestamp>_<name>/`.

## YAML shape

```yaml
name: Service Outage Cartservice
namespace: default
startup:
  enabled: true
  args: []
timings:
  pre_fault_delay_seconds: 60
  post_fault_delay_seconds: 30
traffic:
  enabled: true
  base_url: http://localhost:8080
  duration_seconds: 300
  rps: 1
baseline:
  enabled: true
  duration_seconds: 300
  interval_seconds: 15
fault:
  scenario: service_outage
  target: cartservice
  auto_revert: false
detector:
  enabled: true
  prom_url: http://localhost:9090
  target_deployment: cartservice
  interval_seconds: 10
```

## Supported fault scenarios

- `service_outage`
  - scale a deployment to `0` replicas and restore the original replica count on revert
- `dependency_outage`
  - take down `redis-cart` using the same scale-to-zero mechanism
- `cpu_throttling`
  - patch a deployment's CPU request/limit to constrained values and restore the original values on revert
- `replica_reduction_under_load`
  - scale a target deployment down to a specified replica count and restore the original count on revert

Example fault blocks:

```yaml
fault:
  scenario: cpu_throttling
  target: productcatalogservice
  cpu_request: 25m
  cpu_limit: 50m
  auto_revert: true
  duration_seconds: 180
```

```yaml
fault:
  scenario: replica_reduction_under_load
  target: checkoutservice
  replicas: 1
  auto_revert: true
  duration_seconds: 120
```

## Notes

- `startup.args` are passed directly to `./scripts/start_all.sh`.
- `fault.scenario` maps to the Python `faults/` package through `./scripts/failure_inject.sh`.
- If `fault.auto_revert` is `false`, the runner will revert the fault near the end of the experiment.

- If `detector.enabled` is `true`, the experiment runner starts the monitor loop in the background and writes JSON outputs under `detector_runs/`.
