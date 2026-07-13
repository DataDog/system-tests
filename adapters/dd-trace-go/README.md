# dd-trace-go adapter (native C-FFI)

A third backend for the Temper conformance suite, against the real
[dd-trace-go](https://github.com/DataDog/dd-trace-go) library.

## Why this one is different

Temper has **no Go backend** (`csharp, java, js, lua, mypyc, py, rust`), so —
unlike js/py — the suite itself can't be compiled to Go. Instead this is a
**true native adapter**: dd-trace-go is exposed to C and called in-process via
FFI. No RPC, no subprocess-server.

```
Temper suite (compiled to Python)  ──calls──▶  Tracer ABC
                                                   │  implemented by adapter.py
                                                   ▼
                          ctypes FFI  ──▶  libddtracego.dylib   (go build -buildmode=c-shared)
                                                   │  //export C ABI over dd-trace-go
                                                   ▼
                                            real dd-trace-go tracer
```

- `cshared.go` — `//export`ed C functions (`ddgo_start_span`, `ddgo_set_meta`,
  `ddgo_extract`, `ddgo_inject`, …) over the real tracer.
- `adapter.py` — implements the generated Python `Tracer` ABC by calling those
  C functions through `ctypes`. Ops not yet on the C surface raise
  `NotImplementedError` → the case is skipped.
- `run.py` / `run_one.py` — per-case subprocess (so each case's env is applied
  before the Go tracer initializes) + a shared `ddapm-test-agent`; spans are
  delivered to the agent and read back for `captured_spans()`.

Python is the *driver* here only because it's the mature Temper backend; the
Go↔C FFI is the same regardless of driver.

## Build & run

dd-trace-go **v2.9.1** requires a **Go 1.25** toolchain (its `go.mod` declares
`go 1.25.0`). The repo's default `go` is 1.19, which cannot build v2 and cannot
auto-download a toolchain (auto-toolchain is a Go ≥1.21 feature). Install a
pinned, **stable** Go 1.25 once (do NOT use /tmp):

```
# one-time: stable toolchain under $HOME/toolchains (survives reboots/tmp cleanup)
mkdir -p ~/toolchains/go1.25
curl -fsSL https://go.dev/dl/go1.25.11.darwin-arm64.tar.gz | tar -xz -C ~/toolchains/go1.25
~/toolchains/go1.25/go/bin/go version   # -> go1.25.11 darwin/arm64
```

Build the dylib with that toolchain, then run the suite:

```
cd adapters/dd-trace-go && \
  GOROOT=$HOME/toolchains/go1.25/go GOTOOLCHAIN=local \
  $HOME/toolchains/go1.25/go/bin/go build -buildmode=c-shared -o libddtracego.dylib .
cd ../.. && temper build -b py
PYTHONPATH=adapters/dd-trace-go:temper.out/py/system-tests-redux:temper.out/py/temper-core:temper.out/py/std \
  ./.venv-ddtrace/bin/python adapters/dd-trace-go/run.py
```

Result on dd-trace-go **v2.9.1**: **211/211 passed, 32 skipped** (of 243 total;
0 failures) — up from 182/182 on v1.64.1. The +21 comes from v2 (default W3C
`baggage` propagation → `get_all_D009` newly wired via
`SpanContext.ForeachBaggageItem`, plus D001/D004/D005/D008/D016; W3C phase-3
last-parent-id; the `OTEL_TRACES_SAMPLER` family + attribute mapping) *and* from
pruning the stale v1-era known-diffs list — run_one.py runs every case and only
downgrades a genuine FAIL to a skip, so entries that v2 now passes surfaced as
real passes. The
C surface covers core spans, header extract/inject, the OpenTelemetry span API
(via dd-trace-go's OTel bridge — incl. bidirectional cross-API parenting through
`tracer.SpanFromContext`/`ContextWithSpan`), agent-delivered spans + client
stats, config readback (captured from dd-trace-go's startup CONFIGURATION log via
a custom `WithLogger`), resource updates, and baggage set/get/get-all.

### v1 → v2 API migration notes

- imports moved `gopkg.in/DataDog/dd-trace-go.v1/...` →
  `github.com/DataDog/dd-trace-go/v2/...`.
- the `ddtrace.Span` / `ddtrace.SpanContext` interfaces are gone; the tracer now
  uses concrete `*tracer.Span` / `*tracer.SpanContext` (maps retyped,
  `tracer.StartSpanOption`).
- `SpanContext.TraceID()` now returns a 128-bit hex `string`; use
  `TraceIDLower()` for the low-64 decimal the agent/tests expect.
- a W3C `baggage`-only header extracts to a baggage-only `SpanContext` whose
  `SpanID()` is 0; `ddgo_extract` hands back a synthetic non-zero handle (`x<n>`)
  so the following `StartSpan(ChildOf(...))` inherits the baggage (fixes D009).

### Sampling migration (env translation, go subprocess only)

Contrary to the initial spike hypothesis, the **`DD_TRACE_SAMPLING_RULES` /
`DD_SPAN_SAMPLING_RULES` JSON schema is unchanged between v1 and v2** (same
`service`/`name`/`sample_rate`/`resource`/`tags`/`max_per_second` fields, same
glob semantics — verified against v2's `rules_sampler.go`). The real v2
regression is client-side stats: **`DD_TRACE_STATS_COMPUTATION_ENABLED` now
defaults to `true`**, so when the test-agent advertises `client_drop_p0s` the
tracer drops sampled-out (priority ≤ 0) traces client-side and never sends them.
The conformance sampling cases assert the dropped span's
`_sampling_priority_v1` / `_dd.rule_psr`, which requires the span to reach the
agent. `run.py` therefore defaults **`DD_TRACE_STATS_COMPUTATION_ENABLED=false`
for the go subprocess only** (via the subprocess `env=`), recovering all 7
regressed cases (`trace_sampling.{dropped_by_rule,glob_dropped,resource_dropped,
tags_dropped,tag_metric_mismatch}`, `span_sampling.{sss014,sss015}`).
`library_tracestats.TS001` sets it back to `"1"` in its own case env, so client
stats stay on where a case needs them. **No file under `src/` is modified.**
(Note: dd-trace-go snapshots the environment at dylib-load time, so this must be
real process env — `run.py` supplies it via `subprocess(..., env=...)`; mutating
`os.environ` from Python after load has no effect. For standalone `run_one.py`
isolation runs, export the case env + this var in the shell first.)

## Why not a Rust driver? (the `rust-adapter/` attempt)

The cleaner shape would be a compiled Rust binary: Temper→Rust suite + a Rust
adapter that FFIs the same `.dylib`. `rust-adapter/` implements exactly that.
It's **blocked by a Temper Rust-backend codegen bug**: interface methods with
default parameters (`startSpan(name, parentId, service="", …)`) generate a
`Tracer` wrapper whose `start_span` takes `Option<Option<Arc<String>>>` while the
trait declares `Option<Arc<String>>` (E0053/E0308 in the generated
`system-tests-redux` crate — it doesn't compile). The js/py backends handle the
same defaults fine. Kept here to document the finding; revisit if the Rust
backend fixes default-param interface methods.

## Skips (38)

- **21** — ops not on the C surface (`adapter.py` raises `NotImplementedError`),
  split between additive-but-unwired and genuine v2 API gaps: the remote-config
  seam (7 — dd-trace-go's RC poller doesn't start on plain `tracer.Start`),
  telemetry config (2), wire-encoder span_events (3 — see below),
  `otel_record_exception` (2 — v2's OTel bridge embeds `noop.Span` and does
  **not** override `RecordError`, so it records nothing); and genuine API gaps
  — dd-trace-go's `*Span` has **no public tag removal** (interop
  set/update/remove meta+metric), **no add-link-after-start** (only
  `WithSpanLinks` at creation → span_links), and **no remove-baggage**
  (`remove_D010` / `remove_all_D011`; v2 only exports
  `SetBaggageItem`/`BaggageItem`/`ForeachBaggageItem`).
- **17** — genuine dd-trace-go **v2.9.1** behavioral differences the suite
  surfaces (`run.py:KNOWN_GO_DIFFS`): migrated-b3 style (5); 6 `otel_env_vars`
  cases that assert resolved-config keys (`propagation_style` / `trace_enabled`
  / `otel_enabled` / `log_level`) the adapter's config readback doesn't expose
  (v2 *does* map the underlying `OTEL_*` vars); propagated `_dd.p.*` tags +
  manual-keep override (2); two OTel-bridge specifics (http status remap — v2
  has the remap but the adapter's numeric-attr wiring still yields "0";
  UNSET-after-ERROR); ipv6 agent-url bracketing (1); and `max_bytes_D017` (v2's
  8192-byte baggage cap trims to 3 items vs the expected 2). Entries that v2 now
  passes — default W3C baggage, W3C phase-3, the `OTEL_TRACES_SAMPLER` family +
  attribute mapping, `only_D002`, `agent_unix_url` — were verified and pruned
  from the list.

**span_events (investigated, kept skipped):** v2's OTel bridge *does* implement
`AddEvent` (records events onto the DD span, flushed at `End`), so
`otel_add_event` is wireable. But the `span_events.{native_v04,native_v07,
meta_v05}` cases additionally require the adapter to read back the exact
agent-side wire encoding of those events (type-coded `{type:0,string_value:…}`
for native v04/v07, meta-string form for v05) across three `DD_TRACE_API_VERSION`
values — a separate, version-specific serialization surface not yet wired.
Deferred to keep the 0-failure result stable.

Config readback covers dd_service/env/version, agent url, sample rate, rate
limit, tags, debug, runtime-metrics — the fields dd-trace-go emits in its startup
config log. propagation_style / trace_enabled / otel_enabled aren't mapped from
that log, so the otel_env_vars cases that assert them are among the known-diffs.
