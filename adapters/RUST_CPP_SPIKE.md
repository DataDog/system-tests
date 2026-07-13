# dd-trace-rust + dd-trace-cpp — feasibility spike (verified)

Both are the remaining upstream parametric languages (→ 9/9). Both **libraries build
on macOS arm64** (verified this session); both backends are feasible. Recorded here
so the adapters can be finished quickly (the async-worker infra was down when this
was spiked — see note at bottom).

## dd-trace-rust — NATIVE Temper backend (cleanest; no shim)

Temper has a rust backend, so the suite is already a rust lib crate
(`temper.out/rust/system-tests-redux`). The adapter is a plain rust binary that
path-deps that crate + `temper-core`, `impl`s the suite's `TracerTrait` against
dd-trace-rs, and runs cases in-process. Template for consuming the crate:
`adapters/dd-trace-ruby/shim/src/lib.rs` (`all_cases()`, `Tracer::new(impl)`,
`CapturedSpan`, `CheckResult`). Full ~40-method trait: `temper.out/rust/.../mod.rs`.

### Build (verified)
- `datadog-opentelemetry` is **not on crates.io**; use a git dep:
  `datadog-opentelemetry = { git = "https://github.com/DataDog/dd-trace-rs" }`
  (crate version 0.5.0). `cargo build -p datadog-opentelemetry` → **exit 0** on
  macOS arm64 (stock cargo, no extra system deps).
- dd-trace-rs is **OpenTelemetry-based** — drive it via the `opentelemetry` crate
  API + the Datadog exporter/provider (`datadog_opentelemetry::configuration::
  Config::builder()` → `SdkTracerProvider`). Needs a tokio runtime for the
  exporter's background flush.

### Op → API mapping (from upstream `utils/build/docker/rust/parametric/src/datadog/mod.rs`)
- **start_span**: `get_tracer().span_builder(name).with_attributes([...])` with
  `service.name`, `resource.name`, `span.type`, `operation.name=name`,
  `_dd.top_level=1` (the last prevents libdatadog dropping the chunk). Parent via
  `Context::new().with_remote_span_context(parent.span_context().clone())` +
  `builder.start_with_context(get_tracer(), &ctx)`, else `builder.start(get_tracer())`.
- **ids**: `span_context().span_id()` → `u64::from_be_bytes(.to_bytes())`; trace_id
  → `u128::from_be_bytes(...)` (low64 for the agent decimal).
- **set_meta / set_metric / set_resource**: `span.set_attribute(KeyValue::new(k, v))`
  (resource → `resource.name`).
- **inject/extract**: `global::get_text_map_propagator(|p| p.inject_context(&ctx, &mut injector))`
  / `p.extract(&HeaderExtractor(&map))`; store extracted `Context` by a synthetic id.
- **config**: `dd_config.into()` (the `Config` → map impl) gives the readback.
- **flush**: `tracer_provider.force_flush()`.
- **baggage**: routes are **commented out** in the upstream client → dd-trace-rs
  has no manual baggage API → `unsupported` (as ruby/php).
- **otel_***: dd-trace-rs is OTel-native, so otel_* map to the SAME OTel span API.
- Per-case subprocess + real ddapm-test-agent capture, mirroring `adapters/dd-trace-go/run.py`.

## dd-trace-cpp — host-in-target, reuses the shared cdylib (simplest host)

C++ speaks the C ABI natively, so it `dlopen`s the SAME rust cdylib ruby/php use
(`adapters/dd-trace-ruby/shim/target/debug/libstr_ruby_shim.dylib`) and passes a
plain C++ function as `dispatch` — no FFI marshaling layer. ABI + JSON schema:
`adapters/dd-trace-ruby/CONTRACT.md`. Dispatch logic mirrors
`adapters/dd-trace-ruby/adapter.rb`, implemented against dd-trace-cpp.

### Build (verified)
- `git clone https://github.com/DataDog/dd-trace-cpp` → `cmake -B build
  -DCMAKE_BUILD_TYPE=Release && cmake --build build` → **exit 0**,
  `libdd-trace-cpp.a` produced. It explicitly supports Apple
  (`src/datadog/platform_util_darwin.cpp`).
- **Only blocker was CMake ≥ 3.28** (the repo requires it; stock was 3.25.1).
  `brew install cmake` → 4.4.0 fixes it. Bundles its own curl (slow first build).

### API (dd-trace-cpp manual tracer)
- `datadog::tracing::TracerConfig` + `datadog::tracing::Tracer`; `tracer.create_span()`
  / `create_span_with_options`, `span.set_tag(k,v)`, distributed headers via
  `span.inject(DictWriter)` / `tracer.extract_span(DictReader)`. Reference: the
  dd-trace-cpp repo `examples/` + the system-tests cpp parametric server (fetched
  by `utils/build/docker/cpp/parametric/install_ddtrace.sh`).
- C++ dispatch MUST wrap its body in try/catch → return `{"__error__":...}` (never
  let a C++ exception unwind across the C boundary into rust = UB), like
  `run_one.rb`/`run_one.php`.

## Note on why these aren't finished yet
The two adapters were dispatched to parallel worktree subagents (as requested), but
the async-worker infra failed repeatedly this session: the default `claude-opus-4-8`
(bedrock) hit a deterministic `400 "thinking blocks ... cannot be modified"`, and the
`anthropic/claude-sonnet-4-5` override had no API key. Feasibility + the reference
APIs above are verified; finishing the two adapters is mechanical from here.
