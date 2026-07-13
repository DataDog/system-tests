# Evaluation: parametric tests → Temper portability

Scope: `DataDog/system-tests` `tests/parametric/` — the only meaningful web-app-free
suite. **30 files, 371 test functions.** All already drive the language-agnostic RPC
interface (no weblog), so all are portable *in theory*. This doc assigns each a
**disposition** for the in-memory-capture Temper model (adapter provides the
span-capture + config-readback mechanism; no network from Temper).

## Disposition legend
- **PORT** — pure tracer logic; in-memory captured spans + interface calls suffice. Port first.
- **PORT(config)** — asserts on tracer config readback (env-var driven). Adapter exposes `config()`. Portable.
- **ADAPT(agent)** — needs data only a real test-agent produces (telemetry/stats payloads). Port after a `TestAgent`-style capture seam is added; adapter must surface telemetry/stats events in-memory.
- **DEFER(rc)** — needs agent-driven Remote Config push. No in-memory analog without adapter emulating RC. Defer; likely keep on Python harness.
- **KEEP(native)** — process-level (crash, flare files, /proc discovery). Not pure-Temper; keep native-assisted or on Python harness.

## Counts by disposition
| disposition | ~funcs |
|---|---|
| PORT | ~290 |
| PORT(config) | ~26 |
| ADAPT(agent) | ~17 (telemetry 10–14, stats 7) |
| DEFER(rc) | ~24 |
| KEEP(native) | ~18 |
| **total** | **371** |

~85% (PORT + PORT(config)) portable in the first waves.

## Per-file matrix

| file | funcs | disposition | notes |
|---|---|---|---|
| test_128_bit_traceids.py | 25 | PORT | trace-id width/propagation; pure span+header logic. |
| test_headers_datadog.py | 5 | PORT | inject/extract Datadog headers. |
| test_headers_b3.py | 12 | PORT | B3 single-header. |
| test_headers_b3multi.py | 7 | PORT | B3 multi-header. |
| test_headers_none.py | 6 | PORT | propagation style "none". |
| test_headers_precedence.py | 11 | PORT | propagator precedence ordering. |
| test_headers_tracestate_dd.py | 7 | PORT | `dd=` tracestate encoding. |
| test_headers_tracecontext.py | 38 | PORT | W3C traceparent/tracestate validation; lots of malformed-header cases — pure extract/inject, ideal. |
| test_headers_baggage.py | 17 | PORT | W3C baggage propagation + set/remove. |
| test_span_links.py | 6 | PORT | span links + attribute flattening (`array.0`). **Spike target.** |
| test_span_sampling.py | 18 | PORT | single-span sampling rules → captured span tags. |
| test_sampling_span_tags.py | 11 | PORT | `_dd.p.*` / sampling decision tags. |
| test_trace_sampling.py | 21 | PORT | trace-level sampling rules/priority. |
| test_sampling_delegation.py | 1 | PORT | sampling delegation header. |
| test_span_events.py | 4 | PORT | span events v04/v05/v07 encoding. |
| test_partial_flushing.py | 4 | PORT | partial-flush span counts. |
| test_tracer.py | 6 | PORT | basic span tree/service/resource. |
| test_otel_tracer.py | 2 | PORT | OTel tracer basics. |
| test_otel_span_methods.py | 26 | PORT | OTel span API → captured span mapping. |
| test_otel_api_interoperability.py | 16 | PORT | OTel↔DD interop within one trace. |
| test_otel_span_with_baggage.py | 1 | PORT | OTel + baggage. |
| test_config_consistency.py | 25 | PORT(config) + KEEP(6) | mostly env→config readback + span tags; ~6 use exec/process checks → KEEP. |
| test_otel_env_vars.py | 16 | PORT(config) | OTEL_* env → effective config readback. |
| test_parametric_endpoints.py | 31 | PORT (30) / KEEP(1) | interface conformance; 1 crash endpoint. Re-frame as adapter-conformance harness in Temper. |
| test_library_tracestats.py | 9 | ADAPT(agent) | client-computed stats payloads to agent; needs stats capture seam. |
| test_telemetry.py | 12 | ADAPT(agent) | app-started/telemetry events; needs telemetry capture seam. |
| test_dynamic_configuration.py | 23 | DEFER(rc) (22) / PORT(1) | RC-driven config + capability flags. |
| test_tracer_flare.py | 7 | KEEP(native) | flare zip files + RC trigger. |
| test_crashtracking.py | 3 | KEEP(native) | forces crash, inspects crash report. |
| test_process_discovery.py | 1 | KEEP(native) | reads `/proc` metadata. |

## Wave ordering (drives PLAN phases 4/6)
1. **Wave 1 (spike + core, ~110):** span_links, tracer, span_sampling, sampling_span_tags, span_events, partial_flushing, headers_datadog/b3/b3multi/none.
2. **Wave 2 (~150):** headers_tracecontext, headers_baggage, headers_precedence, tracestate_dd, 128_bit_traceids, trace_sampling, sampling_delegation.
3. **Wave 3 OTel (~61):** otel_span_methods, otel_api_interoperability, otel_tracer, otel_span_with_baggage, otel_env_vars.
4. **Wave 4 config (~45):** config_consistency, parametric_endpoints (as conformance suite).
5. **Wave 5 agent-dependent (~17):** telemetry, library_tracestats — after capture seam.
6. **Deferred / keep-python (~42):** dynamic_configuration (rc), tracer_flare, crashtracking, process_discovery.

## Caveats (not yet verified — flag for spike)
- tracecontext malformed-header assertions need exact byte-level header parsing parity in adapters; in-memory extract must return the *tracer's* interpretation, not a re-parse.
- config-readback requires every adapter to expose effective config identically — today's `config()` endpoint coverage is uneven across languages (feature-parity board). Expect gaps.
- "ADAPT(agent)" assumes telemetry/stats can be surfaced in-memory by the adapter rather than scraped from a real agent; unproven — may force a minimal embedded test-agent for those waves.
