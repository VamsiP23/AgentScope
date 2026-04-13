# Agent Graph

This package now centers on one agent path: a typed-tool ReAct incident agent.

Main files:
- `agent_graph/aci.py`
- `agent_graph/react_agent.py`
- `agent_graph/react_prompt.py`
- `agent_graph/react_support.py`
- `agent_graph/tools/`
- `agent_graph/reasoning/llm.py`

Design:
- `AgentCloudInterface` exposes the observation and action tools used by agents.
- `ReActAgent` runs the investigation loop.
- `react_prompt.py` holds the system prompt.
- `react_support.py` holds shared normalization and signal helpers.
- `tools/` contains the live backend integrations for Kubernetes, Prometheus, Jaeger, and safe actions.

Current entrypoints:
- `python3 ./scripts/run_benchmark_agent.py --agent-type react --backend live ...`
- `python3 ./scripts/run_benchmark_agent.py --agent-type react --backend replay ...`

The older LangGraph workflow agent was removed as part of the cleanup so the repo has one primary agent architecture instead of parallel agent stacks.
