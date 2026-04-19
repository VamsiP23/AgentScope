# Native Bulk Collection Summary

- started_at_utc: 2026-04-18T05:37:39Z
- finished_at_utc: 2026-04-18T05:37:40Z
- target_count: 5
- dry_run: True

| scenario | ready | attempts | collected | failed | status |
| --- | ---: | ---: | ---: | ---: | --- |
| native_service_port_mismatch_productcatalogservice | 5 | 0 | 0 | 0 | target_met |
| native_service_selector_mismatch_cartservice | 5 | 0 | 0 | 0 | target_met |
| native_bad_image_productcatalogservice | 4 | 0 | 0 | 0 | dry_run_missing_1 |
| native_bad_probe_cartservice | 5 | 0 | 0 | 0 | target_met |
| native_scale_zero_recommendationservice | 3 | 0 | 0 | 0 | dry_run_missing_2 |
| native_pod_delete_cartservice | 5 | 0 | 0 | 0 | target_met |
| native_dependency_bad_endpoint_frontend_cartservice | 3 | 0 | 0 | 0 | dry_run_missing_2 |
| native_bad_env_checkoutservice_email | 3 | 0 | 0 | 0 | dry_run_missing_2 |
| native_cpu_limit_throttle_checkoutservice | 3 | 0 | 0 | 0 | dry_run_missing_2 |
| native_memory_limit_oom_cartservice | 3 | 0 | 0 | 0 | dry_run_missing_2 |
| native_cpu_pressure_stress_job | 3 | 0 | 0 | 0 | dry_run_missing_2 |
| native_memory_pressure_stress_job | 3 | 0 | 0 | 0 | dry_run_missing_2 |

## Failed/Skipped Details
- native_bad_image_productcatalogservice: dry_run_missing_1
- native_scale_zero_recommendationservice: dry_run_missing_2
- native_dependency_bad_endpoint_frontend_cartservice: dry_run_missing_2
- native_bad_env_checkoutservice_email: dry_run_missing_2
- native_cpu_limit_throttle_checkoutservice: dry_run_missing_2
- native_memory_limit_oom_cartservice: dry_run_missing_2
- native_cpu_pressure_stress_job: dry_run_missing_2
- native_memory_pressure_stress_job: dry_run_missing_2
