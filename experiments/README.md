# Experiments

The checked-in experiment YAMLs serve two purposes:

- the native benchmark collection flow
- the presentation demo path

The benchmark-grade reproducible evaluation surface is the replay dataset, but these native live experiment files are still the source of the original collected incidents.

## Fault Backend

This repo now keeps only the native Kubernetes fault-injection path implemented in [`faults`](../faults).

Use:

- `fault.kind: native_kubernetes`
- `fault.spec: ...`

## Key Entry Points

- [`scripts/run_experiment.py`](../scripts/run_experiment.py): run one live experiment
- [`scripts/capture_episode_dataset.py`](../scripts/capture_episode_dataset.py): collect and promote replayable episode JSONs from live runs
- [`scripts/run_live_fix_demo.sh`](../scripts/run_live_fix_demo.sh): presentation-friendly native live demo

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
- older exploratory live experiments were intentionally removed so this directory only contains the native experiment definitions relevant to the final benchmark and demo
- if your goal is reproducibility, start from [`REPRODUCIBILITY.md`](../REPRODUCIBILITY.md)
