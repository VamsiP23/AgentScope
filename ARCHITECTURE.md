# AgentScope Architecture

AgentScope is organized as a layered incident-triage benchmark:

1. Environment
   - Online Boutique on Docker Desktop Kubernetes
   - Chaos Mesh faults in `chaosmesh/experiments/`
   - Prometheus, Jaeger, Kubernetes logs/events/state
   - workload scripts in `scripts/generate_traffic.sh` and `scripts/collect_baseline.sh`

2. Agent-Cloud Interface (ACI)
   - `agent_graph/aci.py`
   - observation plane:
     - `get_metrics`
     - `get_traces`
     - `get_logs`
     - `get_k8s_state`
   - safe control plane:
     - `restart_pod`
     - `rollout_restart`
     - `rollout_undo`
     - `patch_resources`
     - `wait_and_monitor`
     - `submit_solution`
   - backend adapters:
     - `agent_graph/tools/prometheus.py`
     - `agent_graph/tools/jaeger.py`
     - `agent_graph/tools/kubernetes.py`
     - `agent_graph/tools/actions.py`

3. Agent policy loop
   - `agent_graph/react_agent.py`
   - ReAct-style uncertainty reduction over typed ACI tools
   - pure ReAct reasoning over evidence, with only search-hygiene and safety guardrails

4. Benchmark problem and evaluation harness
   - problem definitions:
     - `benchmark_suite.yaml`
     - `benchmarking/problem.py`
   - experiment orchestration:
     - `scripts/run_experiment.py`
     - `scripts/run_react_agent.py`
   - run grading:
     - `benchmarking/evaluator.py`

5. Results layer
   - per-run artifacts under `experiment_runs/<run_id>/`
   - aggregate analysis:
     - `benchmarking/results.py`
     - `scripts/aggregate_benchmark_results.py`

Core design rule:

The agent never talks to infrastructure directly. All infrastructure observation and
control goes through the typed, logged ACI.
