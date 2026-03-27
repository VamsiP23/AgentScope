# Experiments

The experiment runner supports Chaos Mesh fault manifests through:
- `fault.filepath`

Current state:
- the runner supports baseline traffic, detection, optional agent execution, and artifact capture
- faults are defined as checked-in Chaos Mesh YAML files under `chaosmesh/experiments/`
- the runner applies and reverts them through `python3 -m faults.cli`

Supported experiment shape:

```yaml
name: Chaos Pod Kill Cartservice Agent
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
  rps: 1
baseline:
  enabled: true
  duration_seconds: 300
  interval_seconds: 15
fault:
  filepath: chaosmesh/experiments/podchaos.yaml
  duration_seconds: 60
  auto_revert: false
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
- `chaos_pod_kill_cartservice_baseline.yaml`
- `chaos_pod_kill_cartservice_agent.yaml`
- `chaos_network_delay_frontend_cartservice_baseline.yaml`
- `chaos_cpu_stress_checkoutservice_baseline.yaml`
- `chaos_dns_cartservice_baseline.yaml`

For a first agent validation run, prefer:
- `chaos_pod_kill_cartservice_agent.yaml`

Why:
- it produces a clean transient incident on a replicated service
- the detector signal is straightforward
- the agent can run in `dry_run` mode without changing cluster state
- it exercises the LLM-backed hypothesize, research, policy, act, and verify stages
