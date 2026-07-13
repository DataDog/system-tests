# Coverage gap survey

Two kinds of gap, measured against DataDog/system-tests `tests/parametric/`
(**371 test functions across 30 files**) and the five live backends
(dd-trace-js, -py, -go, -dotnet, -java).

- **Axis 1 — not ported to Temper:** upstream tests with no case in the suite.
- **Axis 2 — ported but not green everywhere:** cases that pass on some backends
  but are skipped on ≥1 (per-library gaps / verified diffs).

Snapshot: **243** Temper cases cover **~220** distinct upstream functions (~59%);
of the 243, **181 pass on all five** backends and **0 pass on none**. Live pass
counts: py 236, java 218, js 216, go 212, dotnet 209 (of 243).

## Axis 1 — upstream tests not ported

### Fully unported files (0 cases) — 53 functions
| file | fns | why not ported |
|---|--:|---|
| test_parametric_endpoints.py | 31 | out of model — exercises the test-client/HTTP endpoint surface, not tracer behavior |
| test_sampling_span_tags.py | 11 | all-library `@bug` upstream (behavior not settled) |
| test_tracer_flare.py | 7 | native flare artifact, RC-triggered — out of model |
| test_crashtracking.py | 3 | OS crash artifact — out of model |
| test_process_discovery.py | 1 | OS process artifact — out of model |

### Partially ported files (gap = upstream − ported)
| family | ported/upstream | gap | what's missing |
|---|:--:|--:|---|
| dynamic_configuration | 8 / 23 | 15 | RC apply beyond capability + sampling-rate (capability advertise + apply now wired on all five) |
| otel_span_methods | 15 / 26 | 11 | operation-name mapping + array-attr encoding (both-lib `@missing_feature`) |
| telemetry | 2 / 12 | 10 | per-library telemetry config-**name** mapping (only universal names ported) |
| config_consistency | 16 / 25 | 9 | dogstatsd / stable-config-file / rate-limiter variants |
| library_tracestats | 1 / 9 | 8 | client-stats variants (nodejs doesn't compute stats) |
| span_sampling | 11 / 18 | 7 | rate-limiter + dropping-policy (needs agent `client_drop_p0s`) |
| otel_api_interoperability | 9 / 16 | 7 | OTel-view-of-a-DD-span cases (not exposed on js) |
| headers_baggage | 14 / 18 | 4 | remaining baggage edge cases |
| headers_precedence | 7 / 11 | 4 | vacuous / version-sensitive default-order cases |
| span_links | 4 / 6 | 2 | v0.5 wire-link encoding + link-propagated sampling (both-lib `@missing_feature`) |
| partial_flushing | 1 / 4 | 3 | flush-count variants |
| span_events | 3 / 4 | 1 | invalid-attribute discard (not reproducible via add_event) |
| otel_env_vars | 15 / 16 | 1 | one nodejs-config gap |
| otel_tracer | 1 / 2 | 1 | |

Complete families (no axis-1 gap): headers_tracecontext, 128_bit_traceids,
headers_b3, headers_b3multi, headers_none, headers_datadog, headers_tracestate_dd,
trace_sampling, tracer (+SCI), sampling_delegation.

## Axis 2 — ported cases not green on all five backends

181/243 pass on all five; **62** pass on some but skip on ≥1; **0** skip on all five.

Per-backend skip totals: js 27, py 7, go 32, dotnet 34, java 25.

Legend: ✓ pass · ✗ skip. Grouped by family.


**config_consistency**

| case | js | py | go | dotnet | java |
|---|:--:|:--:|:--:|:--:|:--:|
| agent_host_ipv6 | ✓ | ✓ | ✗ | ✗ | ✓ |

**dynamic_configuration**

| case | js | py | go | dotnet | java |
|---|:--:|:--:|:--:|:--:|:--:|
| capability_logs_injection | ✓ | ✓ | ✗ | ✓ | ✓ |
| sampling_rate_override | ✗ | ✓ | ✓ | ✗ | ✓ |

**headers_b3**

| case | js | py | go | dotnet | java |
|---|:--:|:--:|:--:|:--:|:--:|
| migrated_extract_invalid | ✗ | ✓ | ✓ | ✓ | ✓ |
| migrated_extract_valid | ✗ | ✓ | ✗ | ✗ | ✗ |
| migrated_inject_valid | ✗ | ✓ | ✗ | ✗ | ✗ |
| migrated_propagate_invalid | ✗ | ✓ | ✗ | ✗ | ✗ |
| migrated_propagate_valid | ✗ | ✓ | ✗ | ✗ | ✗ |
| migrated_single_key_propagate_valid | ✗ | ✓ | ✗ | ✗ | ✗ |

**headers_baggage**

| case | js | py | go | dotnet | java |
|---|:--:|:--:|:--:|:--:|:--:|
| default_D001 | ✓ | ✓ | ✓ | ✗ | ✓ |
| extract_D005 | ✗ | ✓ | ✓ | ✗ | ✓ |
| get_after_extract_D008 | ✗ | ✗ | ✓ | ✗ | ✓ |
| get_all_D009 | ✗ | ✓ | ✓ | ✗ | ✓ |
| inject_encoding_D004 | ✗ | ✓ | ✓ | ✗ | ✓ |
| max_bytes_D017 | ✗ | ✓ | ✗ | ✗ | ✓ |
| max_items_D016 | ✗ | ✓ | ✓ | ✗ | ✓ |
| only_D002 | ✗ | ✓ | ✓ | ✗ | ✓ |
| remove_D010 | ✓ | ✓ | ✗ | ✓ | ✓ |
| remove_all_D011 | ✓ | ✓ | ✗ | ✓ | ✓ |
| set_disabled_D007 | ✗ | ✓ | ✓ | ✓ | ✓ |

**headers_tracecontext**

| case | js | py | go | dotnet | java |
|---|:--:|:--:|:--:|:--:|:--:|
| duplicated | ✓ | ✓ | ✓ | ✓ | ✗ |
| ts_empty_header | ✓ | ✓ | ✓ | ✓ | ✗ |
| ts_multiple_headers_diff_keys | ✓ | ✓ | ✓ | ✓ | ✗ |
| ts_ows_handling | ✓ | ✓ | ✓ | ✗ | ✓ |

**headers_tracestate_dd**

| case | js | py | go | dotnet | java |
|---|:--:|:--:|:--:|:--:|:--:|
| change_sampling_reset_dm | ✗ | ✗ | ✓ | ✓ | ✓ |
| change_sampling_same_dm | ✗ | ✗ | ✓ | ✓ | ✓ |
| evicts_32 | ✗ | ✗ | ✓ | ✗ | ✓ |
| propagate_propagatedtags | ✓ | ✓ | ✗ | ✓ | ✗ |

**library_tracestats**

| case | js | py | go | dotnet | java |
|---|:--:|:--:|:--:|:--:|:--:|
| TS001 | ✗ | ✓ | ✓ | ✗ | ✗ |

**otel_env_vars**

| case | js | py | go | dotnet | java |
|---|:--:|:--:|:--:|:--:|:--:|
| dd_precedence | ✓ | ✗ | ✗ | ✗ | ✗ |
| exporter_none | ✗ | ✓ | ✗ | ✓ | ✓ |
| log_level | ✓ | ✗ | ✗ | ✗ | ✗ |
| log_level_debug | ✓ | ✓ | ✓ | ✗ | ✗ |
| otel_enabled_precedence | ✗ | ✓ | ✗ | ✗ | ✓ |
| otel_only | ✓ | ✓ | ✗ | ✗ | ✗ |
| sdk_disabled | ✗ | ✓ | ✗ | ✗ | ✓ |

**otel_interop**

| case | js | py | go | dotnet | java |
|---|:--:|:--:|:--:|:--:|:--:|
| nested_dd_root | ✓ | ✓ | ✓ | ✗ | ✓ |
| set_update_remove_meta | ✓ | ✓ | ✗ | ✓ | ✗ |
| set_update_remove_metric | ✓ | ✓ | ✗ | ✓ | ✗ |
| span_links_add | ✓ | ✓ | ✗ | ✗ | ✗ |

**otel_span**

| case | js | py | go | dotnet | java |
|---|:--:|:--:|:--:|:--:|:--:|
| http_status_remap | ✓ | ✓ | ✗ | ✓ | ✗ |
| operation_name_consumer | ✗ | ✓ | ✓ | ✓ | ✓ |
| operation_name_internal | ✗ | ✓ | ✓ | ✓ | ✓ |
| operation_name_mapping | ✗ | ✓ | ✓ | ✓ | ✓ |
| record_exception_error_tags | ✓ | ✓ | ✗ | ✓ | ✓ |
| record_exception_no_error | ✓ | ✓ | ✗ | ✓ | ✓ |
| status_error_unset_ignored | ✓ | ✓ | ✗ | ✓ | ✓ |
| status_ok_final | ✓ | ✗ | ✓ | ✓ | ✓ |

**span_events**

| case | js | py | go | dotnet | java |
|---|:--:|:--:|:--:|:--:|:--:|
| meta_v05 | ✓ | ✓ | ✗ | ✗ | ✓ |
| native_v04 | ✓ | ✓ | ✗ | ✓ | ✗ |
| native_v07 | ✓ | ✓ | ✗ | ✓ | ✗ |

**span_links**

| case | js | py | go | dotnet | java |
|---|:--:|:--:|:--:|:--:|:--:|
| attached_links | ✓ | ✓ | ✗ | ✗ | ✗ |
| from_distributed_datadog | ✓ | ✓ | ✗ | ✗ | ✗ |
| from_distributed_w3c | ✓ | ✓ | ✗ | ✗ | ✗ |
| trace_id_high | ✓ | ✓ | ✗ | ✗ | ✗ |

**span_sampling**

| case | js | py | go | dotnet | java |
|---|:--:|:--:|:--:|:--:|:--:|
| sss011_manual_drop_kept | ✓ | ✓ | ✗ | ✓ | ✓ |

**telemetry**

| case | js | py | go | dotnet | java |
|---|:--:|:--:|:--:|:--:|:--:|
| config_tags | ✓ | ✓ | ✓ | ✓ | ✗ |

**traceids_128bit_tc**

| case | js | py | go | dotnet | java |
|---|:--:|:--:|:--:|:--:|:--:|
| tid_in_chunk_root | ✓ | ✓ | ✓ | ✗ | ✓ |

**tracer**

| case | js | py | go | dotnet | java |
|---|:--:|:--:|:--:|:--:|:--:|
| sci_commit_sha | ✓ | ✓ | ✓ | ✗ | ✓ |
| sci_repository_url | ✓ | ✓ | ✓ | ✗ | ✓ |
| sci_strip_ssh_token | ✗ | ✓ | ✓ | ✓ | ✓ |
| sci_strip_ssh_userpass | ✗ | ✓ | ✓ | ✓ | ✓ |