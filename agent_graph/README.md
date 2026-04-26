# Agent Graph

The repo currently keeps one benchmark-oriented agent stack with three replay/live variants:

- ReAct (`react`)
- Bounded ReAct (`bounded_react`)
- DiagnosticAgent (`diagnostic`)

## Main Files

- [`agent_graph/react_agent.py`](react_agent.py)
- [`agent_graph/diagnostic_agent.py`](diagnostic_agent.py)
- [`agent_graph/aci.py`](aci.py)
- [`agent_graph/tools`](tools)
- [`agent_graph/reasoning/llm.py`](reasoning/llm.py)

## Entry Points

Replay/live generic runner:

```bash
python3 scripts/run_benchmark_agent.py --agent-type bounded_react --backend replay ...
```

Compact one-shot replay runner:

```bash
python3 scripts/run_compact_diagnosis.py --replay-dataset ... --out-dir ...
```

Structured compact replay runner:

```bash
python3 scripts/run_structured_compact_diagnosis.py --replay-dataset ... --out-dir ...
```

## Notes

- the older LangGraph path is not the benchmark surface anymore
- the reproducible comparison work in the paper is replay-first
- live runs are mainly for collection and demo flows
