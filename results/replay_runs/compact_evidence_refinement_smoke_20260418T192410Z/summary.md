# Compact Evidence Refinement Smoke

- Run root: `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/replay_runs/compact_evidence_refinement_smoke_20260418T192410Z`

| Episode | Exact | Family | Action | Submitted | Expected | Seconds |
| --- | --- | --- | --- | --- | --- | ---: |
| native_scale_zero_recommendationservice_001 | True | True | True | native_scale_zero/scale_deployment | native_scale_zero/scale_deployment | 6.078 |
| native_pod_delete_cartservice_001 | True | True | True | native_pod_delete/wait_and_monitor | native_pod_delete/wait_and_monitor | 7.473 |
| native_cpu_pressure_stress_job_001 | False | False | False | /wait_and_monitor | native_cpu_pressure_stress_job/delete_stress_job | 6.71 |
| native_dependency_bad_endpoint_frontend_cartservice_006 | True | True | False | native_dependency_bad_endpoint/patch_resources | native_dependency_bad_endpoint/rollout_undo | 7.861 |
| native_bad_env_checkoutservice_email_005 | False | True | False | native_dependency_bad_endpoint/patch_resources | native_bad_env/rollout_undo | 8.473 |
