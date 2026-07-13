# dd-trace-java adapter (native Java backend)

A fifth backend for the Temper conformance suite, against the real
[dd-trace-java](https://github.com/DataDog/dd-trace-java) library.

## How it works

Temper has a native **`java` backend**, so the suite compiles directly to Java.
This is a hand-written `Adapter implements system_tests_redux.Tracer` over
dd-trace-java's manual surface — the **OpenTelemetry API** (`io.opentelemetry.api`),
which the dd-trace-java javaagent bridges to real DD spans.

```
Temper suite (compiled to Java, temper.out/java)  ──calls──▶  Tracer
                                                                  │  implemented by Adapter.java
                                                                  ▼
                                                     OpenTelemetry API (spanBuilder, …)
                                                                  │  bridged by
                                                                  ▼
                              -javaagent:dd-java-agent.jar  ──▶  real dd-trace-java tracer
                                                                  │  delivers spans
                                                                  ▼
                                                        ddapm-test-agent ──▶ capturedSpans()
```

Like Datadog.Trace v3 (which needs the CLR profiler), dd-trace-java's manual API
is a **no-op without the javaagent**: `Tracer.spanBuilder(...).startSpan()`
returns an `io.opentelemetry.api.trace.PropagatedSpan` with an all-zero,
invalid context. Under `-javaagent:dd-java-agent.jar` (+ `DD_TRACE_OTEL_ENABLED=true`)
it returns a real `datadog.opentelemetry.shim.trace.OtelSpan` that delivers to
the agent. This is the third agent/loader-required backend (go c-shared →
dotnet profiler → java javaagent).

- `Adapter.java` — `Tracer` over the OTel API: `spanBuilder`/`setAttribute`/`end`,
  explicit parent-by-id via `Context`, header extract/inject via the OTel
  `TextMapPropagator`, `capturedSpans()` from the test-agent. Ops without a wired
  backing throw `UnsupportedOperationException` → the case is skipped.
- `Main.java` — orchestrator (starts a `ddapm-test-agent`, runs each case in its
  own JVM launched with the javaagent + the case's env) + per-index run-one +
  `KNOWN_JAVA_DIFFS` (verified genuine gaps, reported as documented skips;
  run-then-downgrade so a listed case that passes still reports PASS).
- `pom.xml` — depends on the generated `system-tests-redux` artifact +
  `opentelemetry-api` + `org.json`; shades to `target/conformance.jar`.

### Adapter details worth knowing
- **JDK 17+** is required (the generated suite is Java 17 bytecode); the adapter
  itself is Java-8-source. dd-trace-java runs fine on 17.
- Each per-case JVM is launched with:
  - `-Ddd.integrations.enabled=false` — **correctness**: stops the agent from
    auto-instrumenting the adapter's own `HttpURLConnection` calls to the
    test-agent as spurious `http.request` spans (the OTel bridge stays on via
    `DD_TRACE_OTEL_ENABLED`). Without this the suite drops from 160 to 58.
  - `-Ddd.trace.telemetry.enabled=false -Ddd.remote.config.enabled=false
    -Ddd.instrumentation.telemetry.enabled=false -Ddd.trace.startup.logs=false`
    — **speed**: cuts agent startup from ~15s to ~2s per case (4.5 min full run
    vs 71 min).
- `startSpan` sets the reserved `operation.name` attribute so the DD operation
  name is the given name (otherwise the bridge derives it from the span kind,
  e.g. `internal`, and puts the OTel span name into `resource`).
- `injectHeaders` lowercases header names — HTTP headers are case-insensitive and
  the shared cases (written for js/py) look them up lowercase, while OTel's B3
  propagator emits mixed-case `X-B3-TraceId`.
- OTel ids are hex; the agent delivers decimal, so ids are converted (span id =
  16 hex → decimal; trace id = low-64 of the 32-hex → decimal).

## Build & run

```sh
temper build -b java
# install the generated artifacts to the local Maven repo (skip artifact signing)
for p in temper-core std system-tests-redux; do
  mvn -q -f temper.out/java/$p/pom.xml install -DskipTests -Dgpg.skip=true
done
mvn -q -f adapters/dd-trace-java/pom.xml package        # -> target/conformance.jar
# download the javaagent (once) into the adapter dir
curl -sL -o adapters/dd-trace-java/dd-java-agent.jar \
  https://repo1.maven.org/maven2/com/datadoghq/dd-java-agent/1.63.2/dd-java-agent-1.63.2.jar
pkill -f ddapm-test-agent
/opt/homebrew/opt/openjdk@17/bin/java -cp adapters/dd-trace-java/target/conformance.jar ddtracejava.Main
# -> NNN/NNN cases passed (dd-trace-java), N skipped
```
(`./setup.sh` / `./run-all.sh` do all of this.)

Result on dd-trace-java **1.63.2**: **218/218 passed, 25 skipped** (of 243).
Covered: core spans, meta/metric tags, header extract/inject
(datadog/b3/b3multi/tracecontext, incl. 128-bit), the **OpenTelemetry span
API + interop** (kind→operation-name mapping, status/record-exception, span
context, cross-API parenting — both `startSpan` and `otelStartSpan` use the OTel
API so a span created by either is visible/parentable through the other), and
**`config()` readback** (read reflectively from dd-trace-java's internal
`datadog.trace.api.Config` on the bootstrap classpath, which reflects the
fully-resolved config incl. OTEL_* env mapping).

## Skips (44)

- **28 unwired ops** (`UnsupportedOperationException`): baggage set/get, span
  links, wire-encoder span_events, telemetry config, remote config / stats, and
  OTel attribute *removal* (`otelRemoveAttribute`/`removeMeta`/`removeMetric` —
  the OTel Span API has no remove, so the two interop remove cases skip).
- **16 verified genuine diffs** (`Main.java:KNOWN_JAVA_DIFFS`): b3 single↔multi
  migration (5, also js/go-skip); W3C baggage propagation not wired via the OTel
  API (2); duplicate traceparent/tracestate headers (3 — the OTel `TextMapGetter`
  is single-value-per-key so the adapter's carrier collapses duplicates,
  nodejs-parity); dd-trace-java adding an extra `_dd.p.ksr` propagated tag (1);
  `http.response.status_code` not remapped to `http.status_code` by the 1.63
  bridge (1, go has the same gap); and config nuances (4): b3 propagation
  reported as `b3multi`/`b3single` vs the canonical `b3` (2 — normalizing would
  hide the multi-vs-single-header interpretation), and no `dd_log_level` from
  `Config` (2). (The agent-url readback and `OTEL_SDK_DISABLED` cases pass: the
  runner skips its `DD_TRACE_AGENT_URL`/`DD_TRACE_OTEL_ENABLED` forcing for those
  config-only cases so the tracer resolves the case's own env.)

`config()` is read reflectively from `datadog.trace.api.Config` (bootstrap
classpath under the agent). `record_exception` sets `error=1` + `error.stack`/
`error.message` via `Span.recordException(Throwable, Attributes)` (the hand-built
event path lands in the events JSON tag only), and `capturedSpans()` parses the
delivered span's `error` field.
