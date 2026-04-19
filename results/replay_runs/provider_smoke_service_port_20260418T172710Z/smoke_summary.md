# Hosted Provider Service-Port Smoke

- Run root: `/Users/aarnavsawant/Documents/CS6365/AgentScope/results/replay_runs/provider_smoke_service_port_20260418T172710Z`
- Agent: compact one-shot
- Dataset: `datasets/episodes/native_service_port_mismatch_productcatalogservice/native_service_port_mismatch_productcatalogservice_005.json`
- Gemini note: first attempt timed out/then hit local SSL verification on retry; final retry passed with `SSL_CERT_FILE` set to certifi.

| Provider | Model | Status | Seconds | Diagnosis | Action | Submitted | Note/Error |
| --- | --- | --- | ---: | --- | --- | --- | --- |
| anthropic | claude-sonnet-4-20250514 | candidate | 6.582 | True | True | native_service_port_mismatch/patch_service_target_port |  |
| openai | gpt-4o-mini | candidate | 6.369 | True | True | native_service_port_mismatch/patch_service_target_port |  |
| gemini | gemini-2.5-flash | error | 30.221 | None | None | None/None | The read operation timed out |
| gemini | gemini-2.5-flash | candidate | 13.539 | True | True | native_service_port_mismatch/patch_service_target_port | retry with SSL_CERT_FILE set to certifi bundle |
