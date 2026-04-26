# Dataset

The committed benchmark dataset lives under [`datasets/episodes`](episodes).

## What Is In The Repo

- replayable episode JSON files grouped by family
- enough metadata to rerun replay benchmarking and regenerate scored outputs
- strict manifest selection under [`configs/episode_sets/native_50.yaml`](../configs/episode_sets/native_50.yaml)

The main report uses the `native_48_strict_good` set, which is defined in that manifest.

## Family Folders

Committed families include:

- `native_bad_image_productcatalogservice`
- `native_bad_probe_cartservice`
- `native_scale_zero_recommendationservice`
- `native_pod_delete_cartservice`
- `native_service_port_mismatch_productcatalogservice`
- `native_service_selector_mismatch_cartservice`
- `native_cpu_limit_throttle_checkoutservice`
- `native_memory_limit_oom_cartservice`
- `native_cpu_pressure_stress_job`
- `native_memory_pressure_stress_job`
- `native_bad_env_checkoutservice_email`
- `native_dependency_bad_endpoint_frontend_cartservice`

## Episode Shape

Each episode JSON contains replayable evidence, initial context, and hidden evaluation data used by the scorer. The replay runners load these files through [`benchmarking/replay.py`](../benchmarking/replay.py).

Some episodes also retain provenance fields such as `source_run_dir` or original `experiment_file` values from the collection pipeline. Those strings are informational only. The older raw collection directories were intentionally pruned from the repo, so reproducibility should rely on the committed replay JSON itself rather than those historical pointers.

## Counting The Strict Set

```bash
python3 - <<'PY'
from pathlib import Path
import yaml
root = Path('.')
payload = yaml.safe_load((root / 'configs/episode_sets/native_50.yaml').read_text())
print(payload['name'], len(payload['episodes']))
PY
```

Expected output:

```text
native_48_strict_good 48
```
