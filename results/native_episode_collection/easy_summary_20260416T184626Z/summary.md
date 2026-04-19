# Easy Native Episode Collection Summary

Run time: 2026-04-16T18:46:26Z

## Outcome

Collected and audited 15 benchmark-ready easy native Kubernetes episodes: 3 per easy scenario.

Counted packages:

- `native_service_port_mismatch_productcatalogservice`: `_003`, `_004`, `_005`
- `native_service_selector_mismatch_cartservice`: `_003`, `_004`, `_005`
- `native_bad_image_productcatalogservice`: `_001`, `_002`, `_003`
- `native_bad_probe_cartservice`: `_002`, `_003`, `_004`
- `native_scale_zero_recommendationservice`: `_001`, `_002`, `_004`

Removed from curated dataset after audit:

- `native_service_port_mismatch_productcatalogservice_001` and `_002`: older packages without replay-visible Service/config evidence.
- `native_service_selector_mismatch_cartservice_001` and `_002`: older packages without the final decisive Service/config evidence layer.
- `native_bad_probe_cartservice_001`: package lacks replay-visible probe-failure text, so it is evidence-insufficient.
- `native_scale_zero_recommendationservice_003`: generated during recovery from the prior scale-zero run and treated as contaminated.

The raw run artifacts were kept under `results/native_episode_collection/`; only the curated packaged dataset JSONs were removed.

## Evidence Audit

All counted packages have non-leaky initial context and replay-smoke-loaded `get_k8s_state`, `get_logs`, `get_metrics`, and `get_traces`.

Decisive replay-visible evidence:

- Service targetPort mismatch: Service port/targetPort, container port, and `service_target_port_mismatch` anomaly.
- Service selector mismatch: Service selector, pod labels, zero ready endpoints, and `service_selector_matches_no_pods` anomaly.
- Bad image: rollout/deployment state plus image-pull failure evidence.
- Bad probe: rollout/deployment state plus readiness probe failure evidence.
- Scale to zero: desired replicas `0`, available replicas `0`, endpoint loss, and scale-down evidence.

Known observability gaps:

- Some selector/probe/scale episodes have weak metrics or missing dependency follow-up counts in the raw evidence summary, but decisive Kubernetes/log evidence is present and replay-callable.
- Traces are present and replay-callable in the counted packages, but they are not the decisive signal for these easy scenarios.

## Raw Artifact Roots

- Bulk run: `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/native_episode_collection/easy_bulk_20260416T180148Z`
- Top-off run: `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/native_episode_collection/easy_topoff_20260416T182707Z`

## Cleanup / Health

Final cleanup check passed: no `agentscope.dev/native-fault=true` resources remained active, `recommendationservice` rolled out successfully after scale-zero revert, all deployments were available, and observability repair passed.
