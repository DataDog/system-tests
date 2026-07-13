# dd-trace-php adapter (shared rust cdylib ⇄ PHP FFI)

A backend for the Temper conformance suite, against the real
[dd-trace-php](https://github.com/DataDog/dd-trace-php) (`ddtrace` Zend
extension).

## Why this one is different

Temper has **no PHP backend** (`csharp, java, js, lua, mypyc, py, rust`), so the
suite itself can't be compiled to PHP. Instead — exactly like the dd-trace-ruby
backend — the suite is compiled to a **rust `cdylib`**, and a PHP process loads
it via **FFI** and drives it in-process. The suite's `Tracer` interface is
implemented by a rust `CallbackTracer` that forwards **every** method to a single
PHP **dispatch** callback as JSON; PHP implements dispatch against dd-trace-php.

The cdylib is the **same one the dd-trace-ruby backend uses** — it is generic
(the frozen C ABI + JSON schema in [../dd-trace-ruby/CONTRACT.md](../dd-trace-ruby/CONTRACT.md)),
so there is nothing PHP-specific to build. This directory is *only* the PHP half.

```
Temper suite (compiled to the shared rust cdylib)  ──runs──▶  CallbackTracer
                                                                 │  every method →
                                                                 ▼
              dispatch(op, args_json)  ◀──── C ABI ────  (rust calls back into PHP)
                    │  PHP FFI closure (native thunk)
                    ▼
              Dispatch::handle(op, args)   (adapter.php)
                    │
                    ▼
              real dd-trace-php (ddtrace ext)  ──spans──▶  ddapm-test-agent
                                                              │  /test/session/traces
                                                              ▼
                                          captured_spans() reads them back
```

- `adapter.php` — `Dispatch::handle($op, $args)` implements the `Tracer` surface
  against the real `ddtrace` extension. Returns a plain PHP value; run_one.php
  JSON-encodes it per CONTRACT. Ops not implemented return
  `["__unsupported__" => true]` → the case SKIPs.
- `run_one.php` — `FFI::cdef`s the ABI, loads the shared cdylib, and passes a
  PHP closure as the C `dispatch` callback (PHP-FFI creates a native thunk and
  marshals the `const char*` args to PHP strings). The closure decodes the args,
  calls `Dispatch::handle`, and returns a **libc-`malloc`'d** NUL-terminated JSON
  string (rust `free()`s it — see "Dispatch malloc" below).
- `run.php` — per-case subprocess runner (so each case's env is applied before
  the extension initializes) + one shared `ddapm-test-agent` on unique ports.
  Sources each case's name/env from the Python registry (`temper.out/py`), the
  same way the dd-trace-go/ruby runners do.

## Versions

- **PHP 8.5.8** (`/opt/homebrew/opt/php/bin/php`) with the bundled **FFI**
  extension.
- **ddtrace 1.21.0** (`pecl install datadog_trace`; on macOS/arm64 it needs the
  pcre2 header on the include path — `CFLAGS=-I$(brew --prefix pcre2)/include`).

## Build & run

```
# one-time: PHP 8.5 (bundles FFI) + the ddtrace extension + a rust toolchain
brew install php pcre2
CFLAGS="-I$(brew --prefix pcre2)/include" pecl install datadog_trace
ln -s ../../.venv-ddtrace .venv-ddtrace                 # shared test-agent venv

# build the shared rust cdylib (owned by the dd-trace-ruby backend)
bash adapters/dd-trace-ruby/build.sh                    # -> ../dd-trace-ruby/shim/target/debug/libstr_ruby_shim.dylib

# generate the Python case registry (run.php reads case env/names from it)
temper build -b py

# OpenTelemetry API/SDK for the otel_* cases (ddtrace bridges OTel -> DD spans)
( cd adapters/dd-trace-php && composer install )        # brew install composer

# run the suite
/opt/homebrew/opt/php/bin/php adapters/dd-trace-php/run.php
```

Run a single case standalone (export the case env first, then point at an agent):

```
DD_TRACE_AGENT_URL=http://127.0.0.1:8126 DD_TRACE_CLI_ENABLED=1 \
DD_TRACE_GENERATE_ROOT_SPAN=0 DD_TRACE_SIDECAR_TRACE_SENDER=0 \
  /opt/homebrew/opt/php/bin/php adapters/dd-trace-php/run_one.php <index>
```

`run_one.php` prints the suite's `PASS/FAIL/SKIP` line and exits `0`/`1`/`2`
(and `3` if the cdylib is missing).

### Required per-case env (set by run.php)

- `DD_TRACE_CLI_ENABLED=1` — trace the CLI SAPI process (off by default).
- `DD_TRACE_GENERATE_ROOT_SPAN=0` — the adapter manages roots itself via
  `\DDTrace\start_trace_span()`, so the auto-generated root span is disabled
  (otherwise every span nests under it).
- `DD_TRACE_SIDECAR_TRACE_SENDER=0` — use the legacy (in-process curl) trace
  sender. The default sidecar sender times out reaching the agent on macOS; the
  legacy sender delivers reliably via `\dd_trace_synchronous_flush()`.

### Dispatch malloc (ownership)

rust owns and `free()`s the string PHP's `dispatch` returns, so PHP must hand
back a **libc-`malloc`'d** buffer (not a PHP-managed one). `run_one.php` resolves
`malloc` via `FFI::cdef('char* malloc(size_t);')`, copies the JSON bytes plus a
trailing NUL into it (`FFI::memcpy`), and returns the raw pointer. A PHP
exception in the closure is caught and marshaled as `{"__error__":…}` rather than
thrown across the C boundary (which would be UB).

## Explicit-parent span management

The conformance model creates spans with an **explicit** `parentId`, but
dd-trace-php auto-parents on its active-span *stack*. The adapter uses the same
primitives as the upstream system-tests PHP parametric client
(`utils/build/docker/php/parametric/server.php`):

- **root** — `\DDTrace\start_trace_span()` (a new trace, `parent_id=0`).
- **child of a local span** — `\DDTrace\switch_stack($parent)` (re-activate the
  parent) + `\DDTrace\create_stack()` (isolate the child on its own stack so
  siblings can be added later) + `\DDTrace\start_span()`.
- **extract** — `\DDTrace\consume_distributed_tracing_headers($cb)` with **no**
  span (a throwaway span would get delivered and break `findOnlySpan`), then read
  the remote parent from `\DDTrace\current_context()["distributed_tracing_parent_id"]`;
  the ambient context is reset afterward so it doesn't leak into later spans.
- **child of an extracted context** — `\DDTrace\start_trace_span()` + re-consume
  the stored carrier, yielding a single delivered span attached to the remote
  parent.
- **finish** — `\DDTrace\switch_stack($span)` + `\DDTrace\close_span()`.
- **inject** — `\DDTrace\switch_stack($span)` + `\DDTrace\generate_distributed_tracing_headers()`.

Spans are read back from the ddapm-test-agent (`captured_spans`/`delivered_spans`),
so the capture reflects the real on-the-wire serialization.

## Ops implemented

**Verified against real dd-trace-php 1.21.0 + a real ddapm-test-agent** (spans
delivered and read back, IDs matching CONTRACT):

- **Core**: `start_span`, `finish_span`, `set_meta`, `set_metric`,
  `set_resource`, `remove_meta`, `remove_metric`, `flush`
  (`\dd_trace_synchronous_flush`), `captured_spans` / `delivered_spans`, `config`
  (via `\dd_trace_env_config(...)`, incl. `dd_log_level`).
- **Propagation**: `extract_headers` / `inject_headers` round-trip
  (`consume`/`generate_distributed_tracing_headers`; datadog / B3 single / b3multi
  / tracecontext, incl. 128-bit; dup headers folded with commas). run.php
  translates the canonical style tokens to dd-trace-php's names (it wants the
  **long** `"B3 single header"` but the **short** `"b3multi"`).
- **Span links**: `add_link` — to a local span (`$span->getLink()`) or to an
  extracted remote context (a manually built `\DDTrace\SpanLink` with the
  128-bit-hex trace id from `_dd.p.tid`); read back from the v0.4
  `meta._dd.span_links` tag.

**OpenTelemetry** (`otel_*`): implemented against the `open-telemetry/api`+`sdk`
composer packages. With `DD_TRACE_OTEL_ENABLED=1`, spans created through the OTel
SDK's `TracerProvider` are bridged to real DD spans by ddtrace (the same OTel-API
path the dotnet/java backends use); `$span->getDDSpan()` gives the DD id so the
existing agent-readback + parenting work unchanged. `captured_spans` is filtered
to adapter-created span ids so the OTel SDK's own resource-detector shell/curl
spans (auto-instrumented by ddtrace) don't leak into `findOnlySpan`.

**Unsupported** (return `{"__unsupported__":true}` → SKIP):

- **Baggage** (`set_baggage`/`get_baggage`/…): dd-trace-php exposes **no** manual
  baggage get/set API (the upstream PHP client has no baggage endpoints either).
- **OTel attribute removal** (`otel_remove_attribute`): the OpenTelemetry span
  API has no attribute-removal method (go/java skip this too).
- **Remote config / stats / telemetry** (`rc_*`, `computed_stats_json`,
  `telemetry_config`): not driveable from the manual API.

## Known genuine diffs (`KNOWN_PHP_DIFFS` in run.php)

Run-then-downgrade: a case is run first and only a **genuine FAIL** is downgraded
to a skip; a listed case that PASSES still reports PASS (the list can't hide a
fix). Each was verified to be real dd-trace-php behavior, not an adapter bug:

- `headers_tracecontext.p3_extract_first`, `headers_precedence.tc_last_extract_first_true`
  — with `datadog,tracecontext` + `DD_TRACE_PROPAGATION_EXTRACT_FIRST=true`,
  dd-trace-php extracts tracecontext, not the first-listed datadog (verified by a
  direct `consume_distributed_tracing_headers` probe).
- `headers_tracecontext.ts_ows_handling` — tracestate optional-whitespace not
  stripped (same as dotnet).
- `headers_tracestate_dd.propagate_propagatedtags` — propagated `_dd.p.dm`
  mechanism value differs (`-0` vs `-4`), same as ruby/go/java.
- `headers_tracestate_dd.keeps_32` / `evicts_32` — tracestate truncated to 31
  list-members (not 32).
- `partial_flushing.one_span` — partial-flush chunk sampling-priority/placement
  differs.
- `otel_env_vars.dd_precedence` — `DD_RUNTIME_METRICS_ENABLED` is not implemented
  in dd-trace-php (the upstream PHP client hard-codes `false`).
- `otel_env_vars.log_level_debug` — `OTEL_LOG_LEVEL=debug` is not mapped to the
  `dd_trace_debug` flag.
- `config_consistency.agent_host_ipv6` — the runner forces `DD_TRACE_AGENT_URL`
  for span delivery, so the `DD_AGENT_HOST`/`DD_TRACE_AGENT_PORT` (ipv6) agent-url
  readback can't be tested (same as ruby/go/dotnet).

## CONTRACT notes / ambiguities

- **trace_id form**: CONTRACT's `CapturedSpan.trace_id` is the **low 64 bits** as
  a decimal string (agent wire format). `start_span`'s returned stub uses
  `\DDTrace\trace_id()` mod 2^64 (via gmp); `captured_spans` uses the agent's
  already-low64 `trace_id`. For span links, the v0.4 `meta._dd.span_links` tag
  carries a 128-bit **hex** trace id, which the adapter splits into decimal
  `trace_id` (low 64) + `trace_id_high` (high 64).
- **json_decode + big ints**: trace/span ids exceed `PHP_INT_MAX`, so the agent
  read-back uses `JSON_BIGINT_AS_STRING` (else they decode to floats like
  `1.39E+19` and corrupt id matching).
- **captured_spans source**: per the task, `captured_spans` reads spans back from
  the ddapm-test-agent (same as `delivered_spans`), not from in-memory span
  objects — so the capture reflects the real serialization.
