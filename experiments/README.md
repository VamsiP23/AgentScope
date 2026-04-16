# Experiments

The benchmark collection path uses native Kubernetes faults implemented in this repository.
The preferred fault shape is:
- `fault.kind: native_kubernetes`
- `fault.spec`: a reversible native fault spec consumed by `python3 -m faults.native`

Current state:
- the runner supports baseline traffic, detection, optional agent execution, and artifact capture
- benchmark collection should use checked-in `native_*` experiment YAMLs
- native faults store rollback state in short-lived ConfigMaps labeled `agentscope.dev/native-fault=true`
- Chaos Mesh and LitmusChaos are not runtime requirements for benchmark collection

Supported experiment shape:

```yaml
name: Native Service Selector Mismatch Cartservice Baseline
namespace: default
startup:
  enabled: false
  args: []
timings:
  pre_fault_delay_seconds: 30
  post_fault_delay_seconds: 60
traffic:
  enabled: true
  base_url: http://localhost:8080
  duration_seconds: 300
  rps: 4
  mode: cart-heavy
baseline:
  enabled: true
  duration_seconds: 300
  interval_seconds: 15
fault:
  kind: native_kubernetes
  duration_seconds: 120
  auto_revert: true
  spec:
    id: selector-mismatch-cartservice
    type: service_selector
    service: cartservice
    selector:
      app: cartservice-missing
detector:
  enabled: true
  prom_url: http://localhost:9090
  target_deployment: cartservice
  interval_seconds: 10
agent:
  enabled: true
  mode: llm
  dry_run: true
  max_iterations: 1
  research_max_tool_calls: 5
  verify_wait_seconds: 30
  jaeger_url: http://localhost:16686
  target_deployment: cartservice
  require_incident_detected: true
  wait_for_incident_timeout_seconds: 90
  wait_for_incident_poll_seconds: 5
```

Checked-in examples:
- `native_service_selector_mismatch_cartservice_baseline.yaml`
- `native_bad_image_productcatalogservice_baseline.yaml`
- `native_bad_probe_cartservice_baseline.yaml`
- `native_cpu_limit_throttle_checkoutservice_baseline.yaml`
- `native_memory_limit_oom_cartservice_baseline.yaml`
- `native_dependency_bad_endpoint_frontend_cartservice_baseline.yaml`

For first collection, prefer:
- `native_service_selector_mismatch_cartservice_baseline.yaml`

Why:
- it produces a clean endpoint/config incident without external fault controllers
- the detector signal is straightforward
- apply/revert is deterministic and self-contained
- it exercises Kubernetes state, service endpoints, Prometheus, and trace evidence collection
