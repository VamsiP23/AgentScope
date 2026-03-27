# LangGraph Migration Layout

This package is the LangGraph-backed incident response agent.

Files:
- `agent_graph/state.py`
- `agent_graph/nodes/detect.py`
- `agent_graph/nodes/hypothesize.py`
- `agent_graph/nodes/research.py`
- `agent_graph/nodes/policy.py`
- `agent_graph/nodes/act.py`
- `agent_graph/nodes/verify.py`
- `agent_graph/workflow.py`
- `agent_graph/cli.py`

Design:
- LangGraph manages state transitions and retry loops
- `agent_graph` owns the full implementation
- the graph is: `detect -> hypothesize -> research -> policy -> act -> verify`
- the graph loops from `verify` back to `hypothesize` when recovery fails and iterations remain
- the detector remains heuristic; the agentic stages are:
  - `Hypothesizer`: ranks root-cause candidates
  - `Researcher`: gathers evidence, optionally by LLM-selected tool calls
  - `Policy`: decides whether evidence supports a hypothesis enough to act
  - `Actor`: selects one bounded remediation action
  - `Verifier`: collects structured recovery evidence and interprets it

Run it after installing `langgraph`:

```bash
python3 -m agent_graph.cli \
  --namespace default \
  --prom-url http://localhost:9090 \
  --jaeger-url http://localhost:16686 \
  --target-deployment cartservice \
  --mode heuristic \
  --research-max-tool-calls 5 \
  --dry-run
```
