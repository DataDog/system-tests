# JS adapter demo (Phase 3 spike)

Hand-written native JS adapter proving the injection boundary — no Temper at
runtime, just the generated library + a native class implementing `Tracer`.
Stands in for a real `dd-trace-js` adapter (Phase 5).

## What it shows
`runSpanWithAttachedLinks(adapter)` — the Temper-compiled conformance test — runs
green against a native JS object that `extends` the generated `Tracer` class and
builds `CapturedSpan`/`CapturedLink` results in-memory. A deliberately broken
adapter fails with precise messages, so the pass is not vacuous.

## Run
```sh
# from repo root
temper build -b js
cp examples/js-adapter-demo/adapter_demo.mjs temper.out/js/system-tests-redux/
cd temper.out/js/system-tests-redux && node adapter_demo.mjs
# -> PASS: runSpanWithAttachedLinks against NativeAdapter
```

The copy step exists only because the spike imports the generated output by
relative path. A real adapter depends on the **published** Temper library
package (`@temperlang/core` resolves transitively) and imports
`runSpanWithAttachedLinks`, `Tracer`, `CapturedSpan`, `CapturedLink` from it.

## Adapter contract (per language)
1. Implement `Tracer`: `startSpan(name, parentId) -> CapturedSpan`,
   `finishSpan(spanId)`, `addLink(spanId, linkToSpanId, attributes)`, `flush()`,
   `capturedSpans() -> CapturedSpan[]`.
2. `parentId == 0` means root. Attributes arrive already-flattened
   (`Map<string,string>`); echo them back unchanged in `CapturedLink`.
3. Call the exported `run*` function with the adapter; assert `result.ok` in the
   native test runner (`result.summary()` on failure).
