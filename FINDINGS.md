# Findings — divergences surfaced by the conformance suite

Running one Temper-authored parametric suite across five backends surfaced a
handful of genuine defects (as opposed to intentional per-library behavior
differences, which live in each adapter's `KNOWN_*_DIFFS` / skip lists). These
are the items worth reporting upstream.

## Temper toolchain

### 1. `java` backend: interface default-arg overloads not generated
**Severity:** blocks compilation of any generated Java that uses an interface
method with default arguments.

`temper build -b java` compiles a Temper interface method with defaults —

```temper
startSpan(name: String, parentId: String,
         service: String = "", resource: String = "", spanType: String = ""): CapturedSpan;
```

— into a **single 5-arg** method on the generated Java interface, but emits the
**2/3/4-arg call sites** unchanged (e.g. `t.startSpan("child", parentId)`). Java
has no default parameters, so the generated suite does not compile:

```
SystemTestsReduxGlobal.java: method startSpan in interface Tracer cannot be applied to given types
  (138 occurrences)
```

The `csharp` backend handles the same source (emits `= null` defaults); js/py
handle it natively. Expected: the Java backend should emit `default` overloads
(or fill defaults at each call site).

**Repro:** `temper build -b java && mvn -f temper.out/java/system-tests-redux/pom.xml compile`
**Workaround in this repo:** `adapters/dd-trace-java/patch_tracer.py` injects the
missing `default` overloads after the build (wired into `setup.sh`/`run-all.sh`).

### 2. `rust` backend: default-param interface methods produce non-compiling code
**Severity:** blocks a pure-Rust driver (`adapters/dd-trace-go/rust-adapter/`).

The same default-parameter interface method generates a `Tracer` wrapper whose
`start_span` takes `Option<Option<Arc<String>>>` while the trait declares
`Option<Arc<String>>` — `E0053`/`E0308` at the generated `mod.rs`. The generated
`system-tests-redux` crate doesn't compile. Same root cause as #1 (interface
default params), different surfacing. js/py/csharp handle the same source.

**Repro:** `temper build -b rust`, then `cargo build` the generated crate.
Kept as documentation in `adapters/dd-trace-go/rust-adapter/` (a Rust FFI driver
that would otherwise be the cleaner shape for the dd-trace-go backend).

## dd-trace-go (v2.9.1)

### 3. Span-event encoder omits zero-valued typed attributes
**Severity:** wire-format divergence from dd-trace-js / dd-trace-py.

dd-trace-go's msgp-generated span-event encoder marks `bool_value`, `int_value`,
and `double_value` `omitempty`, so a span-event attribute whose value is the
zero of its type (`false`, `0`, `0.0`) is **omitted entirely from the v0.4/v0.7
wire payload**. dd-trace-js and dd-trace-py always emit the typed field
(`{"type":1,"bool_value":false}` / `{"type":2,"int_value":0}`). A consumer that
reads span-event attributes by type sees the attribute disappear on go.

Surfaced by `span_events.native_v04` / `native_v07` (exactly the zero-valued
typed-attr assertions fail; all non-zero attrs + arrays match).

### 4. `APM_TRACING_LOGS_INJECTION` remote-config capability not advertised
**Severity:** RC capability gap vs the other libraries.

On `tracer.Start` with a remote-config-capable agent, dd-trace-go/v2.9.1
advertises capability bits `[1, 12, 14, 15, 19, 29, 41, 45]` on `/v0.7/config`
but **not bit 13 (`APM_TRACING_LOGS_INJECTION`)**, which dd-trace-py/js do. So a
`logs_injection` remote-config push would not be honored.

Surfaced by `dynamic_configuration.capability_logs_injection` (the other five
capability bits — sample_rate, http_header_tags, custom_tags, enabled,
sample_rules — are advertised and pass).

## Behavior differences worth confirming (likely intentional, not filed as bugs)

These are documented per-library in the adapters' `KNOWN_*_DIFFS` and are
probably deliberate, but a maintainer may want to confirm:

- **dd-trace-dotnet** honors `DD_GIT_COMMIT_SHA` / `DD_GIT_REPOSITORY_URL` only
  when **both** are set; with one alone it falls back to git metadata embedded in
  the assembly at build time (the .NET SDK's SourceLink). The conformance build
  disables that embedding (`EnableSourceControlManagerQueries=false`) so the env
  is authoritative — 7 of 9 SCI cases pass. The remaining two (`sci_commit_sha`,
  `sci_repository_url`) attach the `_dd.git.*` tag to a **non-root span of the
  chunk** under the profiler, not the logical root the case asserts (same
  placement behavior as 128-bit `_dd.p.tid`). Worth confirming whether SCI tags
  are intended on the local root.
- **dd-trace-dotnet** manual `SpanContextInjector`/`Extractor` never emit/parse a
  W3C `baggage` header (baggage propagation lives only in auto-instrumentation),
  so manual baggage-header cases can't pass on dotnet.
- **dd-trace-java** reports the b3 propagation style by its internal enum name
  (`b3multi` / `b3single`) rather than the canonical `b3` in config readback, and
  attaches an extra `_dd.p.ksr` propagated tag; its telemetry reports `DD_TAGS`
  under the name `DD_TRACE_TAGS`.
- **dd-trace-java** OTel bridge (1.63) doesn't remap the newer semconv
  `http.response.status_code` to `http.status_code`.
