# Coverage ledger

Maps ported Temper conformance functions to their origin in
`DataDog/system-tests` `tests/parametric/`. Status = green on `temper test`
(js + py) **and** the live dd-trace-js adapter.

| family (`tests/parametric/test_*.py`) | ported / upstream | notes |
|---|---|---|
| headers_tracecontext | 38 / 38 | complete (42 cases; some upstream tests split, e.g. W3C phase-3) |
| 128_bit_traceids | 25 / 25 | complete (datadog + b3 + b3multi + w3c) |
| headers_b3 | 12 / 12 | complete (incl. migrated-b3, nodejs-skip per upstream) |
| headers_b3multi | 7 / 7 | complete |
| headers_none | 6 / 6 | complete |
| headers_datadog | 5 / 5 | complete |
| headers_tracestate_dd | 7 / 7 | 3 both-lib skips (dm reset/evict, upstream-faithful) |
| headers_baggage | 13 / 17 | js uses OpenTracing `ot-baggage-*`, not W3C `baggage` (4 nodejs-skip); baggage-only extract nodejs-skip |
| headers_precedence | 7 / 11 | 4 omitted (vacuous / version-sensitive default order) |
| trace_sampling | 20 / 21 | + rule/glob/resource/tag/metric extras |
| span_sampling | 11 / 18 | rate-limiter / dropping-policy deferred (agent + both-lib missing) |
| otel_span_methods | 15 / 26 | operation-name mapping + array-encoding are both-lib `@missing_feature` |
| otel_api_interoperability | 9 / 16 | 7 need OTel-view-of-a-DD-span (not exposed on js) |
| otel_env_vars | 15 / 16 | 3 nodejs-config gaps |
| otel_tracer | 1 / 2 | |
| config_consistency | 16 / 25 | dogstatsd / stable-config-file / rate-limiter deferred |
| span_events | 3 / 4 | v0.4/v0.7 native + v0.5 meta via wire-encoder capture; invalid-attrs not reproducible |
| span_links | 2 / 6 | distributed-datadog done; w3c needs 64-bit traceIdHigh refactor |
| telemetry | 2 / 12 | universal-name configs; per-lib name mapping deferred |
| sampling_delegation | 1 / 1 | complete |
| **partial_flushing** | 1 / 4 | agent-backed; dual |
| **library_tracestats** | 1 / 9 | agent-backed; py-only (nodejs doesn't compute stats) |
| **dynamic_configuration** | 7 / 23 | agent-backed; RC capabilities dual + apply py-only |
| parametric_endpoints | 0 / 31 | out of model (tests the client surface, not the tracer) |
| dynamic_configuration (RC apply beyond sampling) | — | agent-backed, incremental |
| tracer_flare / crashtracking / process_discovery | 0 / 11 | native / RC / OS-artifact — out of model |
| sampling_span_tags | 0 / 11 | all-lib `@bug` upstream |
| tracer | 6 / 6 | complete (+ SCI git-tagging extras; 10 cases) |

**243 cases total.** 

**Eight real libraries, all externally installed:** the live **dd-trace-js**
runner (npm `dd-trace`, currently 5.107.0) passes 216/243 (27 skips), the live
**dd-trace-py** runner (pip `ddtrace` 4.10.4) passes 236/243 (7 skips),
**dd-trace-go** (`dd-trace-go/v2@2.9.1`, native C-FFI) passes 212/243 (32 skips),
**dd-trace-dotnet** (`Datadog.Trace@3.48.0` under the CLR profiler, native
`csharp` backend) passes 209/243 (34 skips), and **dd-trace-java**
(`dd-trace-java@1.63.2` under the javaagent, native `java` backend) passes
218/243 (25 skips). Baggage, remote-config capability/apply, telemetry config,
and span_events were subsequently wired on the go/dotnet/java backends where the
library API allows (see per-backend notes below and GAPS.md for the current
per-case matrix). Every case is verified on js+py (or skipped per-library for
a genuine gap); go and dotnet are additional native backends with their own
verified skip lists (`run.py:KNOWN_GO_DIFFS`, `Program.cs:KnownDotnetDiffs`).
OTel span API is wired on js/py/go. Adapters fold
repeated headers with commas (RFC 7230) so duplicate-header cases run on both,
and the py adapter translates the canonical `"B3 single header"` style to
ddtrace's `"b3"`.

**dd-trace-dotnet backend (209/243, 34 skips):** the suite compiles to C#
(`temper build -b csharp`); `Adapter.cs` implements the generated `ITracer` over
the real `Datadog.Trace` v3.48, run under the Datadog CLR profiler (loaded from
`Datadog.Trace.Bundle`) which the manual + OpenTelemetry APIs require to produce
real spans. Covers spans, meta/metric/resource, header extract/inject, agent-
delivered spans, config readback, the full **OpenTelemetry span API + interop**
(otel_span/otel_tracer green, 8/10 otel_interop — cross-API parenting, resource/
attr updates), and glob/tag sampling rules. Skips (56): baggage, span links,
wire span_events, RC/stats, `otel_record_exception`; + `KnownDotnetDiffs` (30):
SCI git auto-detect, b3 migration, `OTEL_*` config readback not on the public
Settings API, agent-url normalization, tracestate OWS/eviction, 128-bit chunk-
root `_dd.p.tid`, one OTel cross-API-root nuance.

**dd-trace-go backend (211/243, 32 skips):** upgraded to `dd-trace-go/v2@2.9.1`
(requires Go 1.25). Over the v1 baseline this adds W3C baggage propagation +
`get_all_baggage` (6 cases). The sampling env is translated to v2 form in
`run.py` for the go subprocess only (never in `src/`) — v2 defaults
`DD_TRACE_STATS_COMPUTATION_ENABLED=true`, which drops p0 traces client-side, so
the runner forces it off. Remaining skips: no v2 API for remove-baggage,
tag-removal, add-link-after-start, `otel_record_exception` (noop), RC poller,
wire span_events; + `KNOWN_GO_DIFFS` (W3C phase-3, migrated-b3, some `OTEL_*`
config readback, ipv6/unix agent-url).

**dd-trace-java backend (218/243, 25 skips):** the suite compiles to Java
(`temper build -b java`, Java 17 bytecode); `Adapter.java` implements the
generated `Tracer` over the **OpenTelemetry API**, which the dd-trace-java
javaagent bridges to real DD spans (the manual API is a no-op `PropagatedSpan`
without `-javaagent:dd-java-agent.jar` — the third agent/loader-required backend
after go and dotnet). Each case runs in its own JVM with the javaagent +
`-Ddd.integrations.enabled=false` (so the adapter's own test-agent HTTP calls
aren't traced as spurious spans) + telemetry/RC disables (~2s vs ~15s startup).
Covers core spans, meta/metric, header extract/inject
(datadog/b3/b3multi/tracecontext, incl. 128-bit), and the **OpenTelemetry span
API + interop** (otel_span 13/15, otel_interop 6/9, otel_tracer — kind→operation
name, status/record-exception, cross-API parenting, since both APIs share the
OTel context), and **`config()` readback** (service/env/version/sample-rate/tags/
trace-enabled/propagation/rate-limit/runtime-metrics/agent-url/debug/otel-enabled,
read reflectively from dd-trace-java's internal `datadog.trace.api.Config` on the
bootstrap classpath — which reflects OTEL_* env mapping). Skips (44): 28
still-unwired ops (baggage, span links, wire span_events, RC/stats, OTel attribute
*removal* — the OTel Span API has no remove) + 16 `KNOWN_JAVA_DIFFS` (b3 migration,
W3C baggage, duplicate-header carrier collapse (nodejs-parity), extra `_dd.p.ksr`
tag, `http.response.status_code` not remapped by the 1.63 bridge, b3 propagation
reported as b3multi/b3single vs the canonical `b3` (which would hide the
multi-vs-single-header interpretation), and no `dd_log_level` from `Config`).

**dd-trace-ruby backend (193/243, 50 skips):** Ruby has no Temper backend, so —
unlike the others — the suite is compiled to a **rust `cdylib`** (`temper build
-b rust`, unblocked by a one-line default-param codegen patch, `patch_mod.py`)
that a **Ruby process loads via `Fiddle`** and drives in-process against the
`datadog` gem (v2.37, Ruby 3.4) — no RPC. The suite's `Tracer` is implemented as
a single Ruby `dispatch` callback (JSON over a frozen C ABI, `CONTRACT.md`); a
rust `CallbackTracer` forwards every method to it. Covers core spans, meta/metric/
resource, header extract/inject (datadog/b3/b3multi/tracecontext incl. 128-bit,
with canonical→dd-trace-rb style translation), baggage CRUD, span links, and
`config()` readback. Skips (50): 38 unwired ops (otel_* — dd-trace-rb's OTel
bridge needs `opentelemetry-sdk`; wire span_events; RC/stats/telemetry) + 12
`KNOWN_RUBY_DIFFS` (single-span-sampling tags, SCI tag placement, `dd_log_level`/
`OTEL_SDK_DISABLED` config surface, ipv6 agent-url, `_dd.p.dm` value — each
mirrors a diff go/dotnet/java also carry). The FFI boundary is memory-safe:
`catch_unwind` guards every `extern "C"`, matched libc `malloc`/`free` for the
dispatch strings, and Ruby exceptions are marshaled as `{"__error__"}` rather
than thrown across C.

**dd-trace-php backend (205/243, 38 skips):** the second host-in-the-target
backend, reusing the **same rust `cdylib`** as ruby via a different embedder — a
PHP process (with the `ddtrace` Zend extension) `FFI::cdef`s the C ABI, loads the
cdylib, and passes a PHP closure as the `dispatch` callback (PHP-FFI marshals the
`const char*` args to PHP strings + creates a native thunk). dd-trace-php 1.21,
PHP 8.5. The suite's explicit `parentId` is reconciled with dd-trace-php's
active-span *stack* using the same primitives as the upstream PHP parametric
client: `start_trace_span` for roots, `switch_stack`/`create_stack` for children,
`consume_distributed_tracing_headers` (span-less) for extract, and
`generate_distributed_tracing_headers` for inject; delivery via the legacy sender
(`DD_TRACE_SIDECAR_TRACE_SENDER=0`) + synchronous flush, read back from the
test-agent. Covers core spans, meta/metric/resource (+ removal), span links
(local + to an extracted context, parsed from the v0.4 `_dd.span_links` meta
tag), header extract/inject, `config()` readback, and the **OpenTelemetry span
API + interop** (via `open-telemetry/api`+`sdk` from composer +
`DD_TRACE_OTEL_ENABLED=1`, which ddtrace bridges to real DD spans — spans created
through the OTel SDK's `TracerProvider` share the DD active-span context, so
cross-API parenting works; captured spans are filtered to adapter-created ids so
the OTel SDK's own resource-detector shell/curl spans don't leak in). Skips (38):
26 unwired ops (dd-trace-php exposes no manual baggage API — as upstream; OTel
attribute *removal* — the OTel API has none, as go/java; RC/stats/telemetry not
driveable from the manual API) + 12 `KNOWN_PHP_DIFFS` (`datadog,tracecontext`
extraction precedence, tracestate OWS + 31-member truncation, `_dd.p.dm` value,
partial-flush chunk priority, `DD_RUNTIME_METRICS_ENABLED`/`OTEL_LOG_LEVEL`/
`OTEL_SDK_DISABLED` config surface, OTel `http.response.status_code` not
remapped, ipv6 agent-url — each verified against real dd-trace-php, several
shared with the java backend). Same memory-safe FFI boundary as ruby (matched libc `malloc`/`free`,
PHP exceptions marshaled as `{"__error__"}` not thrown across C).

**dd-trace-rust backend (151/243, 92 skips):** the cleanest integration of all
eight — Temper has a native rust target, so the suite is generated as the
`system-tests-redux` rust *lib crate* and the adapter is a plain rust binary that
path-deps it and implements `TracerTrait` against real dd-trace-rs
(`datadog-opentelemetry` v0.5.0, an OpenTelemetry-based tracer) in-process — no
FFI, no cdylib, no C ABI. Spans export to a real ddapm-test-agent and are read
back over HTTP by `captured_spans()`. Covers core spans, meta/metric/resource,
datadog/b3/b3multi/tracecontext extract+inject, parenting, flush, and config
readback (via dd-trace-rs's parsed `Config`). Skips (92): 32 unsupported ops
(manual baggage — commented out in the upstream rust parametric client; OTel
attribute/link removal; RC/stats/telemetry) + 60 `KNOWN_RUST_DIFFS`, each a
verified genuine gap in the young tracer (no `_dd.p.tid` 128-bit tag; no
single-span sampling; OTEL_* env/config mapping absent; no `_dd.git.*` SCI tags;
tag-based sampling rules never match because OTel decides sampling at span start;
tracestate edge-case retention; `_dd.p.dm` value; `DD_TAGS` space form). Each was
confirmed against the real delivered span, and basic cases in each family pass —
the suite doing its job of surfacing an early tracer's gaps.

### Skip fidelity vs upstream system-tests
Upstream-faithful: nodejs OTel operation-name mapping (26 nodejs marks), python
DD_LOG_LEVEL (`@missing_feature python`), nodejs dup-header reconciliation.
Local-only (would pass in normal system-tests — this checkout/adapter, not the
library): python B3-single (ddtrace-4.10 style string), python sample-rate
readback, python+nodejs dup-header / baggage-extract carrier limit, nodejs
baggage header propagation / OTel name mapping (dd-trace-js v6-pre).

Ported: **241** of 371 parametric functions (incl. test_tracer.py SCI git
tagging: repository-url / commit-sha on the chunk-root span + 7 credential-strip
variants; the two `ssh://user:pass@` strip cases are nodejs-skipped — dd-trace-js
5.107 mangles them to `null/...`, while dd-trace-py strips correctly). The in-repo fake validates the
**14** `fakeSupported` cases (js+py); the remaining 109 are adapter-only
(tracer codecs / sampling decisions / config readback that only a real tracer
can judge). Live runs: **dd-trace-js 120/123** (3 nodejs-skips) and
**dd-trace-py 120/123** (3 skips). The hex module's unsigned 64-bit hex→decimal
handles ids > 2^63, so B3 / tracecontext 128-bit id comparisons are exact, and
the adapters capture formatted agent-wire spans (so single-span sampling tags
etc. are visible).

span_sampling not yet ported (7 of 18): rate-limiter + sleep cases (sss008/013),
probabilistic 100-span (sss009), stats-computation (sss010), and dropping-policy
cases needing test-agent `client_drop_p0s` (sss016/017).

## Interface surface exercised so far
spans (root/child, service/resource/type), `setMeta`/`setMetric`, span links +
flattened attributes, Datadog header `extractHeaders`/`injectHeaders`,
sampling-priority / origin / `_dd.p.dm` propagation, in-memory `capturedSpans`,
and **env-parametrized cases** (propagation style) via the `ConformanceCase`
registry.

## Env dimension (solved)
Many parametric tests set `library_env`. Each `ConformanceCase` carries its env
as data; the adapter runs each case under that env (dd-trace-js: one subprocess
per case, mirroring system-tests' container-per-env). The Temper test logic
stays env-agnostic. Proven non-vacuous: `headers_none.extract` only passes
because the tracer is actually built with `...STYLE_EXTRACT=none`.

## fakeSupported / skip mechanism
`ConformanceCase.fakeSupported` (default true) marks behavior-heavy cases the
in-repo FakeTracer can't model without reimplementing a tracer (sampling-rule
evaluation). Those are skipped by the in-repo validation loop and run only
against real adapters. This is the first use of a skip concept; a per-library
missing-feature variant can follow the same shape when a real tracer needs to
opt out of a case.

## Notes / deferrals
- `test_span_events.py` cases are `_test_`-prefixed upstream (disabled; complex
  typed-attribute encoding) — skipped.
- Sampling cases rely on the real tracer's decision; the FakeTracer does not
  evaluate `DD_TRACE_SAMPLING_RULES`.

## Current snapshot (auto-summary)

**243 cases** — dd-trace-js **216/243** (27 skips), dd-trace-py **236/243** (7 skips).

Families now covered (beyond the table above): span_links (attached + distributed-datadog),
span_events (v0.4/v0.7 native + v0.5 meta, via wire-encoder capture), otel_span methods,
otel_interop (9: cross-API meta/metric/resource/links, bidirectional parenting, concurrent +
nested traces), telemetry config (env + tags), sampling_delegation, headers families
(datadog/none/b3/b3multi/precedence/tracecontext 38/38/tracestate/baggage), trace_sampling,
config_consistency, 128-bit trace ids.

### Agent-backed families (real `ddapm-test-agent` subprocess; additive, `needsAgent` flag)
- **partial_flushing.one_span** — dual (py via delivered-spans from the agent; js via the
  processor→exporter capture).
- **library_tracestats.TS001** — py-only (nodejs doesn't compute stats, upstream
  `@missing_feature`); asserts the `/v0.6/stats` bucket the agent received.
- **dynamic_configuration** — RC capability advertisement (6 cases, **dual**: js via a
  short-lived `rc-poll.mjs` helper that polls RC against the same agent) + RC apply
  (`sampling_rate_override`, py-only: the apply loop needs the same tracer instance).

### Skip accounting
js skips (27) and py skips (7) are each one of: (a) upstream `@missing_feature`/`@bug` on that
library (faithful — e.g. nodejs migrated-b3, operation-name mapping, stats; python DD_LOG_LEVEL,
OK→ERROR); (b) a verified dd-trace-js behavior difference (OpenTracing `ot-baggage-*` instead of
the W3C `baggage` header; ssh credential mangling); or (c) the adapter's synchronous-harness
limitation for js's async background work (only `dynamic_configuration.sampling_rate_override`
remains here — js's RC poller/stats writer can't be driven from a synchronous run function,
whereas py's background threads progress during synchronous polling).
