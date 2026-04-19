# Claude DiagnosticAgent Compact Dependency10

- Generated: `2026-04-19T07:43:20Z`
- Run root: `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/replay_runs/claude_diagnostic_compact_dependency10_20260419T0735Z`
- Evaluated: 10/10
- Exact/family/action: 2/10 / 5/10 / 6/10

| # | Episode | Status | Seconds | Exact | Family | Action | Submitted | Expected |
|---:|---|---|---:|---:|---:|---:|---|---|
| 1 | `native_dependency_bad_endpoint_frontend_cartservice_002` | ok | 30.794 | False | True | True | `native_bad_env/rollout_undo` | `native_dependency_bad_endpoint/rollout_undo` |
| 2 | `native_dependency_bad_endpoint_frontend_cartservice_003` | ok | 31.313 | True | True | True | `native_dependency_bad_endpoint/rollout_undo` | `native_dependency_bad_endpoint/rollout_undo` |
| 3 | `native_dependency_bad_endpoint_frontend_cartservice_004` | ok | 31.893 | False | True | True | `native_bad_env/rollout_undo` | `native_dependency_bad_endpoint/rollout_undo` |
| 4 | `native_dependency_bad_endpoint_frontend_cartservice_005` | ok | 39.035 | True | True | True | `native_dependency_bad_endpoint/rollout_undo` | `native_dependency_bad_endpoint/rollout_undo` |
| 5 | `native_dependency_bad_endpoint_frontend_cartservice_006` | ok | 28.925 | False | True | True | `native_bad_env/rollout_undo` | `native_dependency_bad_endpoint/rollout_undo` |
| 6 | `native_bad_env_checkoutservice_email_001` | ok | 31.808 | False | False | False | `native_cpu_limit_throttle/patch_resources` | `native_bad_env/rollout_undo` |
| 7 | `native_bad_env_checkoutservice_email_002` | ok | 35.547 | False | False | False | `native_pod_delete/wait_and_monitor` | `native_bad_env/rollout_undo` |
| 8 | `native_bad_env_checkoutservice_email_003` | ok | 32.587 | False | False | False | `native_dependency_bad_endpoint/` | `native_bad_env/rollout_undo` |
| 9 | `native_bad_env_checkoutservice_email_004` | ok | 32.925 | False | False | True | `native_bad_probe_rollout/rollout_undo` | `native_bad_env/rollout_undo` |
| 10 | `native_bad_env_checkoutservice_email_005` | ok | 33.242 | False | False | False | `native_dependency_bad_endpoint/` | `native_bad_env/rollout_undo` |
