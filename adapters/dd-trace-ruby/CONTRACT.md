# dd-trace-ruby FFI contract (rust cdylib ⇄ Ruby)

The Temper suite compiles to a rust `cdylib`; a Ruby process loads it via `Fiddle`
and drives it. The suite's `Tracer` interface is implemented by a rust
`CallbackTracer` that forwards **every** method to a single Ruby **dispatch**
callback as JSON. Ruby implements dispatch against dd-trace-rb.

This file is the frozen interface between the two halves. Both sides code to it.

## C ABI (exported by the cdylib)

```c
// number of conformance cases
int32_t str_case_count(void);

// Dispatch callback: rust -> Ruby, once per Tracer method call.
//   op        : snake_case Tracer method name, e.g. "start_span", "captured_spans"
//   args_json : JSON array of positional args (see "args" below)
//   returns   : a C-malloc'd (libc malloc) NUL-terminated UTF-8 JSON string of the
//               result (see "results"). rust reads it and calls free() on it.
//               For Void methods return malloc'd "null".
typedef char* (*Dispatch)(const char* op, const char* args_json);

// Run case `index` against a CallbackTracer wired to `dispatch`.
//   returns a rust-malloc'd string: "PASS <name>" | "FAIL <name>:\n<summary>" |
//           "SKIP <name> (<reason>)". Caller frees via str_free.
char* str_run_case(int32_t index, Dispatch dispatch);

// name of case `index` (rust-malloc'd; free via str_free)
char* str_case_name(int32_t index);

void  str_free(char* p);   // frees strings returned by str_run_case / str_case_name
```

**Ownership:** rust frees (via `libc::free`) the string Ruby's `dispatch` returns,
so Ruby MUST return a `malloc`'d copy (e.g. `Fiddle.malloc` + write bytes + NUL, or
a C `strdup`). Ruby frees strings from `str_run_case`/`str_case_name` via `str_free`.
`NotImplementedError`/unsupported ops: Ruby returns malloc'd `{"__unsupported__":true}`;
rust turns that into the suite's skip path (panic caught → SKIP).

## args_json — positional, by the Tracer signature (src/tracer_api.temper)

Encode each arg in order:
- `String` → JSON string; `Float64`/`int` → JSON number; `bool` → JSON bool.
- `List<Entry<String,String>>` (extract_headers) → `[["k","v"],...]` (preserves dup keys).
- `Map<String,String>` (add_link attrs, otel_record_exception attrs) → JSON object.
- `List<EventAttr>` (otel_add_event) → `[{"key":..,"kind":..,"values":[..]}, ...]`.

## results — the method's return value as JSON

- `Void` → `null`
- `String` → JSON string; `bool` → JSON bool
- `Map<String,String>` (config, get_all_baggage) → JSON object
- `CapturedSpan` → object with keys:
  `trace_id, span_id, parent_id, name, service, resource, span_type` (strings),
  `meta` (object str→str), `metrics` (object str→number),
  `links` (array of CapturedLink), `error` (int or null)
- `List<CapturedSpan>` (captured_spans, delivered_spans) → array of the above
- `CapturedLink` → `{span_id, trace_id, trace_id_high, attributes:{}}` (strings + object)
- `OtelSpanContextInfo` (otel_span_context) → `{trace_id_hex, span_id_hex}`
- `List<TelemetryConfigItem>` (telemetry_config) → `[{name, value, origin}, ...]`

## Method list

The full `Tracer` method set + signatures is `src/tracer_api.temper` (and the rust
trait `temper.out/rust/system-tests-redux/src/mod.rs` `trait TracerTrait`). `op` is
the snake_case method name. Ruby may implement a subset; unimplemented ops return
`{"__unsupported__":true}` so the case SKIPs (matching the other adapters' idiom).

## Example

`start_span("web.request", "0", "svc", "/x", "web")` →
dispatch(`"start_span"`, `["web.request","0","svc","/x","web"]`) →
Ruby returns malloc'd `{"trace_id":"123","span_id":"456","parent_id":"0","name":"web.request","service":"svc","resource":"/x","span_type":"web","meta":{},"metrics":{},"links":[],"error":null}`.
