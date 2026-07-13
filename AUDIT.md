# Fidelity audit

Round verifying each ported case tests the same thing as its
`DataDog/system-tests` original (no vacuous / "dummy" tests).

## Method
- Enumerated all 93 `run*` functions / 108 registered cases.
- Scanned for tautologies (`isTrue(true...)`), zero-assertion bodies, and
  self-comparisons. Zero-inline-assert functions were traced into their shared
  helpers (`assertKept`, `assertNotSss`, `checkInjectedB3`, `b3Check64/128`,
  `assertRegenerated`, `checkVariant`) and confirmed to make real assertions.
- Compared each family's assertions against the original Python test asserts.

## Findings & dispositions
- **Worker-authored families faithful** (no changes needed):
  - `headers_tracecontext_more` (26): malformed cases assert trace-id
    regenerated; valid cases assert preserved; tracestate cases assert member
    retention. `runTsIncludedTpMissing`'s equal-member-count assert matches the
    upstream (which was specifically updated to that check).
  - `traceids_128bit_b3` / `_tc`: real id correspondence
    (`hexLow64ToDecimal == span.traceId`), `_dd.p.tid` 16-hex/zero-lower/
    timestamp validation, starts-with checks. The earlier signed-Int64 worry was
    resolved by the unsigned hex→decimal conversion.
  - `headers_tracestate_more` (origin/propagatedtags): asserts exact
    `x-datadog-tags` + `dd=` member items. One origin variant (`synthetics~;=web,z`,
    invalid-char escaping) intentionally omitted — documented in-file.
- **Fixed: `headers_precedence`** — the original ports covered only 2 of the 6
  input variants per style and dropped the cross-format id correspondence. Rewrote
  all four style tests (Datadog / tracecontext / tracecontext,Datadog /
  Datadog,tracecontext) to run all 6 variants each, asserting which context wins,
  header presence/absence, tracestate member counts/`dd=`/`foo` retention, and
  `x-datadog-*` ⇄ W3C trace/parent id equality via `hexLow64ToDecimal` /
  `hexToDecimal`. Still 102/102 against live dd-trace-js.
- **Author's own families** (`span_links`, `tracer`, `headers_datadog`,
  `headers_none`, `trace_sampling`, `span_sampling`, `headers_b3`/`b3multi`,
  `traceids_128bit` Datadog, baggage, otel): each assertion was probe-verified
  against real dd-trace-js when authored; re-reviewed, no vacuous asserts.

## Known, deliberate deviations (not dummies)
- `otel_span.set_attributes` asserts the span name is the literal `operation`
  (dd-trace-js v6-pre does not remap span kind → operation name). The case's
  core intent — OTel `setAttribute` maps to span meta — is asserted exactly. The
  separate name-mapping assertion lives in `otel_span.operation_name_mapping`,
  marked nodejs-unsupported.
- nodejs-`unsupported` cases (6) are skipped, not faked: baggage header
  propagation and OTel operation-name mapping are genuinely absent from this
  dd-trace-js checkout.
- Duplicate-header tracecontext cases (`duplicated`, `ts_empty_header`,
  `ts_multiple_headers_diff_keys`) are nodejs-unsupported (the adapter's header
  carrier collapses duplicate keys, as dd-trace-js itself does); assertions are
  written leniently for libraries that do reconcile duplicates.

## Result
All non-skipped cases make real, original-equivalent assertions. Precedence was
the one materially incomplete family and is now complete.

## Round 2 — agent seam, wire-capture, OTel interop (241 cases)

Fidelity review of the families added after the initial audit.

- **span_events (native v0.4/v0.7 + meta v0.5)** — highest fidelity: asserts the
  **agent-wire** serialization decoded from the real msgpack payload (typed
  `{type,*_value}` for native; string-attr `meta.events` JSON for v0.5), i.e. it
  tests the tracer's encoder, not the adapter. Timestamp assertion omitted (js
  uses wall-clock for OTel event time; py honors the passed value). `invalid_
  attributes` dropped — neither lib discards the invalid inputs via `add_event`,
  so the discard behavior isn't reproducible.
- **otel_api_interoperability (9)** — resource/links/parenting/concurrent/nested
  assert real cross-API behavior on one underlying span, matched by span id
  (robust to js/py naming differences). The set/update/remove meta+metric cases
  create the span via the OTel API (both API views exist on both libs) rather
  than the DD API as upstream does; the interop mechanism is symmetric, noted
  in-file. Afterlife (post-end) no-op writes verified on both.
- **telemetry (config_env/config_tags)** — asserts the app-started telemetry
  configuration (name/value/origin). Only universally-named configs
  (DD_SERVICE/ENV/VERSION/TAGS/HEADER_TAGS); per-library config-name divergence
  (the upstream `telemetry_name_mapping`) is why the rest are deferred, not faked.
- **Agent-backed (partial_flushing / library_tracestats / dynamic_configuration)**
  — assert what a **real ddapm-test-agent** received on the wire: delivered spans,
  the `/v0.6/stats` bucket, and `/v0.7/config` capabilities + apply_state. This is
  the same receiver the upstream suite uses, so fidelity is high. Per-library
  status is genuine, not a shortcut:
  - `partial_flushing` dual — py reads the agent; js reads the processor→exporter
    hook (the delivery-decision point; Node's event loop can't be driven from a
    synchronous run function to round-trip an async agent send).
  - `library_tracestats` py-only — nodejs doesn't compute stats (upstream
    `@missing_feature`).
  - `dynamic_configuration` capabilities dual — js drives the async RC poll via a
    short-lived `rc-poll.mjs` helper against the same agent (capability
    advertisement is a property of the library build). `sampling_rate_override`
    (RC apply) py-only — its apply loop needs the same tracer instance.
- **Verified real (fail without env):** sampling_delegation, config_consistency
  env cases, otel_env_vars, telemetry, dynamic_configuration — all fail via
  `run-one` with no env.

No vacuous cases found. Remaining per-library skips are one of: upstream
`@missing_feature`/`@bug` on that library, a verified dd-trace-js behavior
difference (OpenTracing baggage; ssh credential mangling), or the synchronous-
harness limitation for js's async background work (only
`dynamic_configuration.sampling_rate_override` + the stats family).

## Round 3 — dd-trace-go v2.9.1 + dd-trace-dotnet v3 (CLR profiler)

Fidelity review of the two library upgrades that raised go 182→203 and dotnet
156→185. Focus: any place the new setup could pass a case for the wrong reason.

- **dd-trace-dotnet `error.message` alias — genuine, not fabricated.** Probed
  `otel_span.record_exception_error_tags`: the delivered span carries `error=1`,
  `error.stack`, and `error.msg` **all produced by the library's OTel bridge**;
  the adapter adds only `error.message` as a copy of the lib's `error.msg` (DD's
  native key) to match the js/py-canonical key the shared cases assert. The
  error *state* is the tracer's; only the key name is normalized — the same
  class of per-library normalization as the py adapter's `"B3 single header"`→
  `"b3"`. Documented in the adapter README.
- **dd-trace-dotnet OTel via `ActivitySource` — exercises the real DD bridge.**
  The passing cases include bridge-only logic the adapter cannot fake: span
  **kind**→DD operation name (`operation_name_mapping`/`_consumer`/`_internal`),
  span **name**→`resource`, and `http.response.status_code`→`http.status_code`
  (`http_status_remap`). These are computed inside DD's OpenTelemetry bridge
  under the profiler, so their passing is real evidence the bridge is engaged.
- **dd-trace-dotnet profiler pollution — contained.** The profiler auto-
  instruments HttpClient; the adapter's own agent reads would appear as spurious
  client spans. `DD_TRACE_HttpMessageHandler_ENABLED=false` +
  `HttpSocketsHandler=false` suppress that. Count-sensitive cases (e.g.
  `tracer.top_level_attributes` "trace has 2 spans", the interop concurrent/
  nested cases) pass in the full 185/185 run, which would break on any leaked
  auto-instrumented span — so no pollution reaches assertions.
- **dd-trace-go `stats-off` translation — faithful + non-vacuous.** v2 defaults
  `DD_TRACE_STATS_COMPUTATION_ENABLED=true`, which makes the tracer drop p0
  traces client-side when the agent advertises `client_drop_p0s`, so a
  rule-dropped span never reaches the agent for inspection. `run.py` forces it
  off for the go subprocess only (never in `src/`). Probed
  `trace_sampling.dropped_by_rule`: the delivered span shows
  `_sampling_priority_v1=-1`, `_dd.rule_psr=0` — i.e. the **sampler** made the
  drop decision per the rule; stats-off only restored delivery of the already-
  decided span, it does not alter the decision under test. Fails without the
  sampling env (non-vacuous).
- **dd-trace-go honest known-diffs, list pruned.** `run_one.py` now runs every
  case and downgrades only a genuine FAIL to a documented skip (mirroring the
  dotnet `KnownDotnetDiffs` model); a listed diff that now passes still reports
  PASS. This surfaced 15 stale v1-era `KNOWN_GO_DIFFS` entries that v2 actually
  handles (default W3C baggage, W3C phase-3, the `OTEL_TRACES_SAMPLER` family,
  `only_D002`, `agent_unix_url`), verified stable-passing across runs and pruned.
  Spot-checked `headers_tracecontext.p3_trace_ids_differ`: passes with its
  `DD_TRACE_PROPAGATION_STYLE=datadog,tracecontext` env, fails without it — a
  real phase-3 assertion, not a vacuous pass.

**Remaining go/dotnet skips are genuine**: no public API (remove-baggage,
tag-removal, add-link-after-start, `otel_record_exception` = noop in go's v2
bridge, RC pollers, wire span_events read-back) or verified behavior diffs
(migrated-b3, ipv6 agent-url, resolved-config keys the adapter's config surface
doesn't expose). No fake-green found across the two upgrades.

## Result (round 3)
All four backends (js 214, py 234, go 203, dotnet 185) make real, original-
equivalent assertions; every non-pass is a documented genuine skip. The two
adapter normalizations (dotnet `error.msg`→`error.message`, go per-subprocess
`stats-off`) are behavior-preserving and documented.
