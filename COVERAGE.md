# Coverage ledger

Maps ported Temper conformance functions to their origin in
`DataDog/system-tests` `tests/parametric/`. Status = green on `temper test`
(js + py) **and** the live dd-trace-js adapter.

| Temper `run*` | origin file::test | status |
|---|---|---|
| `runSpanWithAttachedLinks` | test_span_links.py::test_span_with_attached_links | ✅ |
| `runTracerTopLevelAttributes` | test_tracer.py::test_tracer_span_top_level_attributes | ✅ |
| `runHeadersExtractDatadogD001` | test_headers_datadog.py::...extract_datadog_D001 | ✅ |
| `runHeadersExtractDatadogInvalidD002` | test_headers_datadog.py::...extract_datadog_invalid_D002 | ✅ |
| `runHeadersInjectDatadogD003` | test_headers_datadog.py::...inject_datadog_D003 | ✅ |
| `runHeadersPropagateDatadogD004` | test_headers_datadog.py::...propagate_datadog_D004 | ✅ |
| `runHeadersExtractInjectInvalidD005` | test_headers_datadog.py::...extractandinject_datadog_invalid_D005 | ✅ |
| `runHeadersNoneExtract` | test_headers_none.py::test_headers_none_extract | ✅ (env) |
| `runHeadersNoneExtractWithOtherPropagators` | test_headers_none.py::test_headers_none_extract_with_other_propagators | ✅ (env) |
| `runTraceSampledByRuleExactMatch` | test_trace_sampling.py::...sampled_by_trace_sampling_rule_exact_match | ✅ (env, adapter-only) |
| `runTraceDroppedByRule` | test_trace_sampling.py::test_trace_dropped_by_trace_sampling_rule | ✅ (env, adapter-only) |
| `runB3multi*` (extract/inject/propagate valid+invalid, case-insensitive) | test_headers_b3multi.py (6) | ✅ (env, adapter-only) |
| `runB3Single*` (extract/inject/propagate valid+invalid) | test_headers_b3.py (5) | ✅ (env, adapter-only) |
| `runTp*` (valid + 6 malformed-traceparent rejections) | test_headers_tracecontext.py (7) | ✅ (env, adapter-only) |
| `runSss*` (match/no-match/glob/multi-rule/precedence/parent-child/manual-drop) | test_span_sampling.py (11 of 18) | ✅ (env, adapter-only) |
| `runTracestateSamplingPriority` (8 variants) | test_headers_tracestate_dd.py::...propagate_samplingpriority | ✅ (env, adapter-only) |
| `runPrecedence{Datadog,Tracecontext,TcDd,DdTc}` | test_headers_precedence.py (4 style tests) | ✅ (env, adapter-only) |
| `runDd128*` (propagation, tid long/short/chars, prop+gen, gen on/off/default) | test_128_bit_traceids.py (8 Datadog cases) | ✅ (env, adapter-only) |
| `runTp*`/`runTs*` (26: malformed version/parent-id/flags, header name/casing, tracestate handling, OWS) | test_headers_tracecontext.py (remaining) | ✅ (env, adapter-only; 3 nodejs-skip) |
| `runB3Single128*`/`runB3Multi128*` (8) | test_128_bit_traceids.py (B3 single + b3multi) | ✅ (env, adapter-only) |
| `runW3c128*` (9) | test_128_bit_traceids.py (W3C tracecontext) | ✅ (env, adapter-only) |
| `runTracestateOrigin` / `runTracestatePropagatedTags` | test_headers_tracestate_dd.py (origin + propagated tags) | ✅ (env, adapter-only) |

| `runBaggage*` (set/get D006, remove D010, remove_all D011, +extract/inject) | test_headers_baggage.py (5) | ✅ (3 live+fake, 2 nodejs-skip) |
| `runOtel*` (set_attributes, is_recording, span_context, operation_name) | test_otel_span_methods.py (4) | ✅ (3 live, 1 nodejs-skip) |
| `runConfig*` (service/version/env/tags, override, rate-limit default, agent http/unix url) | test_config_consistency.py (7) | ✅ (env, adapter-only; 6 verified fail-without-env) |
| `runOtelEnvVars*`/samplers/precedence | test_otel_env_vars.py (8) | ✅ (7 live, 1 nodejs-skip log precedence) |

**Two real libraries, both externally installed:** the live **dd-trace-js**
runner (npm `dd-trace`, currently 5.107.0) passes 214/241 (27 skips) and the live
**dd-trace-py** runner (pip `ddtrace` 4.10.4) passes 234/241 (7 skips). Every
case is verified on both languages (or skipped per-library for a genuine gap). OTel span API is wired on both. Adapters fold
repeated headers with commas (RFC 7230) so duplicate-header cases run on both,
and the py adapter translates the canonical `"B3 single header"` style to
ddtrace's `"b3"`.

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
