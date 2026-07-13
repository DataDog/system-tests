# dd-trace-dotnet adapter (native C# backend)

A fourth backend for the Temper conformance suite, against the real
[dd-trace-dotnet](https://github.com/DataDog/dd-trace-dotnet) (`Datadog.Trace`)
library.

## How it works

Temper has a native **`csharp` backend**, so — like js/py, and unlike go — the
suite compiles directly to C#. This is a hand-written adapter class implementing
the generated `ITracer` interface against the real `Datadog.Trace` manual API
(`Tracer.Instance.StartActive`, `SpanContextExtractor`/`SpanContextInjector`,
`Tracer.Instance.Settings` for config readback).

```
Temper suite (compiled to C#, temper.out/csharp)  ──calls──▶  ITracer
                                                                  │  implemented by Adapter.cs
                                                                  ▼
                                                     real Datadog.Trace tracer
                                                                  │  delivers spans
                                                                  ▼
                                                        ddapm-test-agent  ──▶ CapturedSpans()
```

- `Adapter.cs` — `Adapter : SystemTestsRedux.ITracer` over the real tracer. The
  Datadog manual API (`Tracer.Instance.StartActive`) and the OpenTelemetry bridge
  (`System.Diagnostics.ActivitySource`) are both wired; ops with no backing API
  (baggage, span links, wire span-events, telemetry, remote-config, client stats)
  throw `NotImplementedException` → the case is skipped.
- `Program.cs` — no args = orchestrator (starts a `ddapm-test-agent` on a free
  port, runs each case in its own subprocess so env — including the CLR-profiler
  variables — is applied before the tracer initializes); `<index>` = run one case.
  Holds `KnownDotnetDiffs` (verified genuine library behavior gaps, reported as
  documented skips).
- `DdTraceDotnet.csproj` — references the generated `SystemTestsRedux.csproj`,
  `Datadog.Trace` **3.48.0** and `Datadog.Trace.Bundle` **3.48.0** (the native
  profiler home); targets `net6.0` with `RollForward=LatestMajor` (runs on the
  installed .NET 10 runtime).

## Datadog.Trace **v3** under the CLR profiler

dd-trace-dotnet's docs state: *"Starting with v3.0.0, custom instrumentation
requires you also use automatic instrumentation."* Under v3.48 the standalone
manual API returns **no-op spans** (`Datadog.Trace.Stubs.NullSpanContext`,
trace/span ids = 0) unless the CLR profiler is loaded — the manual API classes
are stubs the profiler rewrites at runtime.

This adapter therefore runs every case **under the CLR profiler** (automatic
instrumentation), which the orchestrator bakes into each per-case subprocess:

```
CORECLR_ENABLE_PROFILING=1
CORECLR_PROFILER={846F5F1C-F9AE-4B07-969E-05C26BC060D8}
CORECLR_PROFILER_PATH=<bundle>/content/datadog/osx/Datadog.Trace.ClrProfiler.Native.dylib
DD_DOTNET_TRACER_HOME=<bundle>/content/datadog
DD_TRACE_OTEL_ENABLED=true
DD_TRACE_HttpMessageHandler_ENABLED=false     # suppress auto-instrumenting the
DD_TRACE_HttpSocketsHandler_ENABLED=false     # adapter's own agent HTTP calls
```

The native profiler home comes from the **`Datadog.Trace.Bundle`** NuGet package
(pinned to the `Datadog.Trace` version): its `content/datadog` dir holds the
managed tracer + the `osx/…ClrProfiler.Native.dylib`. `Program.cs:ResolveProfiler`
globs `~/.nuget/packages/datadog.trace.bundle/<version>/content/datadog/osx/…` at
runtime and fails with a clear message if it is absent.

Running under the profiler unlocks the **OpenTelemetry bridge**: with
`DD_TRACE_OTEL_ENABLED=true` DD registers an `ActivityListener`, so the adapter's
`Otel*` methods (backed by `System.Diagnostics.ActivitySource`) produce real DD
spans and the OTel↔DD cross-API interop works.

Adapter details worth knowing: real ids live on `span.Context` (the deprecated
`span.SpanId`/`.TraceId` return 0); Activity ids are hex while DD reports
unsigned-64 decimals, so `OtelStartSpan` converts (DD trace id = low 64 bits of
the 128-bit trace id); spans must be finished with `span.Finish()` for
`ForceFlushAsync` to deliver mid-process; the adapter also sets
`Settings.Exporter.AgentUri` via `Tracer.Configure`; a genuine root started while
another span is active is pinned with `SpanContext.None` (DD manual API) to escape
the profiler's unified ambient context — but only when a span is actually active,
since `SpanContext.None` otherwise suppresses 128-bit trace-id generation.

## Build & run

```sh
temper build -b csharp
dotnet build adapters/dd-trace-dotnet   # restores Datadog.Trace + Datadog.Trace.Bundle 3.48.0
dotnet adapters/dd-trace-dotnet/bin/Debug/net6.0/conformance.dll
# -> NNN/NNN cases passed (dd-trace-dotnet), N skipped
```

The orchestrator owns its own `ddapm-test-agent` on a free port (started/killed by
PID — it never `pkill`s the agent globally). Run one case by index (needs an agent
on `DD_TRACE_AGENT_URL` and the CLR-profiler env; see above):
```sh
DD_TRACE_AGENT_URL=http://127.0.0.1:8126 \
  CORECLR_ENABLE_PROFILING=1 CORECLR_PROFILER='{846F5F1C-F9AE-4B07-969E-05C26BC060D8}' \
  CORECLR_PROFILER_PATH=$HOME/.nuget/packages/datadog.trace.bundle/3.48.0/content/datadog/osx/Datadog.Trace.ClrProfiler.Native.dylib \
  DD_DOTNET_TRACER_HOME=$HOME/.nuget/packages/datadog.trace.bundle/3.48.0/content/datadog \
  DD_TRACE_OTEL_ENABLED=true \
  dotnet adapters/dd-trace-dotnet/bin/Debug/net6.0/conformance.dll <index>
```

Result on Datadog.Trace v3.48.0 + CLR profiler: **209/209 passed, 34 skipped** (of
241 total). Covered: core spans, meta/metric tags, resource, header extract/inject
(datadog/b3/b3multi/tracecontext/tracestate), 128-bit trace-id generation, agent-
delivered spans, config readback, and — new under v3+profiler — the full
`otel_span`/`otel_span_more`/`otel_tracer` OpenTelemetry-bridge families plus most
of `otel_interop` (OTel↔DD cross-API parenting, meta/metric, resource update).

## Skips (56)

- **26 unwired ops** — no backing API used in this adapter: **baggage**
  (no baggage inject/extract wired), **span links** (`SpanLink`/add-link),
  wire-encoder span_events, telemetry config, remote config /
  dynamic_configuration, client stats. These throw `NotImplementedException`.
- **30 genuine v3.48 + profiler behavior diffs** (`Program.cs:KnownDotnetDiffs`,
  each verified against delivered output):
  - **SCI** auto-detects git from the real repo and ignores `DD_GIT_*` (9).
  - **b3 single↔multi migration** not implemented (5, also a js-skip).
  - **no baggage propagation** wired (2).
  - **`OTEL_*`→DD config readback** (6): the mapping *does* resolve under
    v3+profiler (verified: `dd_service`, sample rate, tags), but these assert
    resolved keys — `dd_trace_propagation_style`, `dd_runtime_metrics_enabled`,
    `dd_log_level`, `dd_trace_debug`, `dd_trace_otel_enabled` — that the public
    `Datadog.Trace` Settings API does not expose. A config-readback gap, not a
    mapping gap.
  - **agent-url normalization** — ipv6 bracketing, unix-socket form (4).
  - **`otel_interop.nested_dd_root`** (1): under the profiler's unified context an
    OTel-API root created inside an active DD-API span is parented to it, and the
    ActivitySource path has no root-escape (DD's manual API has `SpanContext.None`).
  - **tracestate** optional-whitespace / 32-member eviction (2); and
    **`traceids_128bit_tc.tid_in_chunk_root`** (1) — v3+profiler serializes
    `_dd.p.tid` onto a non-root span of the chunk, not the chunk root.

Note vs. the earlier v2.61 standalone adapter: v3 gained **glob/tag sampling
rules** and **`DD_TAGS` space-separator splitting** (those 6 cases now PASS and
were removed from `KnownDotnetDiffs`), while the profiler unlocked the ~40 OTel
cases that were previously unwired skips.

### Adapter normalization (for transparency)
`Adapter.cs` aliases DD's native error key to the suite's canonical name: DD's
OpenTelemetry bridge records an exception/error-status description under
`error.msg`, but the shared cases (matching dd-trace-js/py) assert
`error.message`, so the adapter mirrors the message to `error.message`. The
underlying behavior (exception recorded, `error=1`, `error.stack`) is genuine
from the library — only the key name is normalized. This is the same kind of
per-library normalization as the py adapter translating the canonical
`"B3 single header"` propagation-style name to ddtrace's `"b3"`.
