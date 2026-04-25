# Experiments

The checked-in experiment YAMLs serve two purposes:

- live collection and calibration
- the presentation demo path

The benchmark-grade reproducible evaluation surface is the replay dataset, but these live experiment files are still the source of the original collected incidents.

## Preferred Fault Backend

The repo now prefers native Kubernetes fault injection implemented in [`faults`](/Users/aarnavsawant/Documents/CS6365/AgentScope/faults) over external chaos frameworks for benchmark collection.

Use:

- `fault.kind: native_kubernetes`
- `fault.spec: ...`

## Key Entry Points

- [`scripts/run_experiment.py`](/Users/aarnavsawant/Documents/CS6365/AgentScope/scripts/run_experiment.py): run one live experiment
- [`scripts/collect_episode.py`](/Users/aarnavsawant/Documents/CS6365/AgentScope/scripts/collect_episode.py): collect and promote a replayable episode from a live run
- [`scripts/run_live_fix_demo.sh`](/Users/aarnavsawant/Documents/CS6365/AgentScope/scripts/run_live_fix_demo.sh): presentation-friendly native live demo

## Example Live Run

```bash
python3 scripts/run_experiment.py experiments/native_bad_image_productcatalogservice_live_demo.yaml
```

## Example Collection Run

```bash
python3 scripts/run_experiment.py experiments/native_service_selector_mismatch_cartservice_baseline.yaml
```

## Notes

- most benchmark analysis in the report comes from replay evaluation, not repeated live runs
- live runs are best used for collection, smoke validation, and demos
- if your goal is reproducibility, start from [`REPRODUCIBILITY.md`](/Users/aarnavsawant/Documents/CS6365/AgentScope/REPRODUCIBILITY.md)
