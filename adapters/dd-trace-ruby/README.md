# dd-trace-ruby adapter (rust cdylib ⇄ Ruby FFI)

A backend for the Temper conformance suite, against the real
[dd-trace-rb](https://github.com/DataDog/dd-trace-rb) (`datadog` gem).

## Why this one is different

Temper has **no Ruby backend** (`csharp, java, js, lua, mypyc, py, rust`), so the
suite itself can't be compiled to Ruby. Instead the suite is compiled to a
**rust `cdylib`**, and a Ruby process loads it via `Fiddle` and drives it. The
suite's `Tracer` interface is implemented by a rust `CallbackTracer` that
forwards **every** method to a single Ruby **dispatch** callback as JSON; Ruby
implements dispatch against dd-trace-rb.

```
Temper suite (compiled to rust cdylib)  ──runs──▶  CallbackTracer
                                                       │  every method →
                                                       ▼
              dispatch(op, args_json)  ◀── C ABI ──   (rust calls back into Ruby)
                    │  Fiddle::Closure
                    ▼
              Dispatch.handle(op, args)   (adapter.rb)
                    │
                    ▼
              real dd-trace-rb tracer  ──spans──▶  ddapm-test-agent
                                                       │  /test/session/traces
                                                       ▼
                                       captured_spans() reads them back
```

The frozen C ABI + JSON schema is [CONTRACT.md](CONTRACT.md).

- `adapter.rb` — `Dispatch.handle(op, args)` implements the `Tracer` surface
  against a real `datadog` tracer. Returns a plain Ruby value; run_one.rb
  JSON-encodes it per CONTRACT. Ops not implemented return
  `{"__unsupported__":true}` → the case SKIPs.
- `run_one.rb` — loads the cdylib with `Fiddle`, builds a
  `Fiddle::Closure::BlockCaller` for `dispatch`, and calls
  `str_run_case(index, dispatch)`. The closure decodes the op + args C strings,
  calls `Dispatch.handle`, and returns a **libc-`malloc`'d** NUL-terminated JSON
  string (rust `free()`s it — see "Dispatch malloc" below).
- `run.rb` — per-case subprocess runner (so each case's env is applied before
  `require "datadog"`) + one shared `ddapm-test-agent` on unique ports. Sources
  each case's name/env from the Python registry (`temper.out/py`), the same way
  the dd-trace-go runner does.

## Versions

- **Ruby 3.4.3** (`/opt/homebrew/opt/ruby/bin/ruby`). The system Ruby 2.7.5 is
  EOL and is **not** used.
- **datadog (dd-trace-rb) 2.37.0** (`gem "datadog", "~> 2.37"`).

## Build & run

```
# one-time: Ruby 3.4 + the datadog gem
/opt/homebrew/opt/ruby/bin/gem install datadog          # or: bundle install
ln -s ../../.venv-ddtrace .venv-ddtrace                 # shared test-agent venv

# build the rust cdylib (the conformance suite; sibling build)
(cd shim && cargo build)                                # -> shim/target/debug/libstr_ruby_shim.dylib

# generate the Python case registry (run.rb reads case env/names from it)
temper build -b py

# run the suite
/opt/homebrew/opt/ruby/bin/ruby adapters/dd-trace-ruby/run.rb
```

Run a single case standalone (export the case env first, then point at an agent):

```
DD_TRACE_AGENT_URL=http://127.0.0.1:8126 \
  /opt/homebrew/opt/ruby/bin/ruby adapters/dd-trace-ruby/run_one.rb <index>
```

`run_one.rb` prints the suite's `PASS/FAIL/SKIP` line and exits `0`/`1`/`2`
(and `3` if the cdylib is missing).

### Dispatch malloc (ownership)

rust owns and `free()`s the string Ruby's `dispatch` returns, so Ruby must hand
back a **libc-`malloc`'d** buffer (not a Ruby-GC'd one). `run_one.rb` resolves
`malloc` from libc via `Fiddle.dlopen(nil)`, copies the JSON bytes plus a
trailing NUL into it, and returns the raw pointer. Ruby frees the strings it
gets back from `str_run_case`/`str_case_name` via the cdylib's `str_free`.

### codegen / cdylib note

The cdylib (`shim/`) is built by the sibling task from the Temper-generated rust
crate (`temper.out/rust/system-tests-redux`). If the Temper rust backend has the
default-parameter interface codegen bug (interface methods with defaults, e.g.
`startSpan(name, parentId, service="", …)`, generating mismatched
`Option<Option<…>>` signatures — see the dd-trace-go `rust-adapter/` note), the
shim's `CallbackTracer` needs the corresponding codegen patch to compile. The
Ruby half of this adapter (this directory's `.rb`/Gemfile) is unaffected: it only
codes to the frozen C ABI in CONTRACT.md.

## Ops implemented

**Verified standalone against real dd-trace-rb 2.37.0 + a real ddapm-test-agent**
(driving `Dispatch.handle` directly, asserting the span is delivered to the
agent and the read-back JSON matches CONTRACT):

- **Core**: `start_span` (name/parent/service/resource/type, decimal
  trace_id[low64]/span_id, explicit-parent nesting via `TraceDigest` +
  `continue_from`), `finish_span`, `set_meta` (`set_tag`), `set_metric`
  (`set_metric`), `flush` (`Datadog::Tracing.shutdown!`), `captured_spans` /
  `delivered_spans` (read back from the agent `/test/session/traces`), `config`.
- **Propagation**: `extract_headers` / `inject_headers` round-trip (via
  `Datadog::Tracing::Contrib::HTTP.extract`/`.inject` — the configured
  propagator; dup headers folded with commas; baggage-only contexts kept as
  `bgctx<n>` handles).
- **Baggage**: `set_baggage` / `get_baggage` / `get_all_baggage` /
  `remove_baggage` / `remove_all_baggage` (trace-level baggage hash).
- **Links / interop**: `add_link` (`SpanLink`), `set_resource`, `remove_meta`
  (`clear_tag`), `remove_metric` (`clear_metric`).

**Unsupported** (return `{"__unsupported__":true}` → SKIP):

- **OpenTelemetry** (`otel_*`, `wire_span_events_json`,
  `wire_span_meta_events_json`): dd-trace-rb ships an OTel bridge
  (`datadog/opentelemetry`), but it only activates when the `opentelemetry-sdk`
  gem is installed (it `prepend`s onto `OpenTelemetry::*`). That gem is not in
  the Gemfile, so these SKIP. To enable: add `gem "opentelemetry-sdk"` and
  `require "datadog/opentelemetry"` + set the DD tracer provider, then wire the
  `otel_*` ops in `adapter.rb`.
- **Remote config / stats / telemetry** (`rc_capabilities_csv`,
  `rc_apply_sampling_rate`, `computed_stats_json`, `telemetry_config`): agent-
  interaction / telemetry-readback surfaces not yet wired.

## CONTRACT notes / ambiguities

- **trace_id form**: CONTRACT's `CapturedSpan.trace_id` is the **low 64 bits**
  as a decimal string (matching the agent wire + the py adapter's `_low64`).
  dd-trace-rb's `SpanOperation#trace_id` is the full 128-bit id; the high 64
  bits land in `_dd.p.tid` meta on the wire. `start_span`'s returned stub uses
  `trace_id & (2**64-1)`; `captured_spans` uses the agent's already-low64
  `trace_id`.
- **captured_spans source**: per the task, `captured_spans` reads spans back
  from the ddapm-test-agent (same as `delivered_spans`), not from in-memory span
  objects — so the capture reflects the real serialization. This requires
  `flush` first; `flush` uses `shutdown!` (synchronous), which is terminal for
  the tracer — fine for the per-case subprocess model.
- **error field**: `start_span`'s stub returns `error: null` (span not finished
  yet); the agent-backed capture returns the integer `error` from the wire.
