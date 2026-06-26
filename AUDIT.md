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
