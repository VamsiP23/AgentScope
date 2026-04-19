# Native Bulk Collection Summary

- started_at_utc: 2026-04-17T05:20:08Z
- finished_at_utc: 2026-04-17T05:20:08Z
- target_count: 3
- dry_run: True

| scenario | ready | attempts | collected | failed | status |
| --- | ---: | ---: | ---: | ---: | --- |
| native_service_port_mismatch_productcatalogservice | 3 | 0 | 0 | 0 | target_met |
| native_service_selector_mismatch_cartservice | 3 | 0 | 0 | 0 | target_met |
| native_bad_image_productcatalogservice | 3 | 0 | 0 | 0 | target_met |
| native_bad_probe_cartservice | 3 | 0 | 0 | 0 | target_met |
| native_scale_zero_recommendationservice | 3 | 0 | 0 | 0 | target_met |
| native_pod_delete_cartservice | 3 | 0 | 0 | 0 | target_met |
| native_dependency_bad_endpoint_frontend_cartservice | 3 | 0 | 0 | 0 | target_met |
| native_cpu_limit_throttle_checkoutservice | 2 | 0 | 0 | 0 | dry_run_missing_1 |
| native_memory_limit_oom_cartservice | 0 | 0 | 0 | 0 | dry_run_missing_3 |
| native_cpu_pressure_stress_job | 0 | 0 | 0 | 0 | dry_run_missing_3 |
| native_memory_pressure_stress_job | 0 | 0 | 0 | 0 | dry_run_missing_3 |
| native_bad_env_checkoutservice_email | 0 | 0 | 0 | 0 | dry_run_missing_3 |

## Failed/Skipped Details
- native_cpu_limit_throttle_checkoutservice: dry_run_missing_1
- native_memory_limit_oom_cartservice: dry_run_missing_3
- native_cpu_pressure_stress_job: dry_run_missing_3
- native_memory_pressure_stress_job: dry_run_missing_3
- native_bad_env_checkoutservice_email: dry_run_missing_3
