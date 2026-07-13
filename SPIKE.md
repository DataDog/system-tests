# Phase 3 spike — results

**Goal:** prove the end-to-end seam — one ported parametric test, written once in
Temper, runs green on js + py via `temper test`, and a *native* adapter (no
Temper at runtime) can drive the compiled test against an injected tracer.

**Test ported:** `test_span_with_attached_links` from
`tests/parametric/test_span_links.py` (spans + span-to-span links + flattened
attribute round-trip).

## Outcome: ✅ proven

| step | result |
|---|---|
| `temper test -b js` | `Tests passed: 1 of 1` |
| `temper test -b py` | `Tests passed: 1 of 1` |
| native JS adapter drives `runSpanWithAttachedLinks` | `PASS` |
| deliberately broken adapter | fails with 5 precise messages (not vacuous) |

## Resolved unknowns
- **Injection mechanism (the headline risk):** *not* a global registry / `@connected`.
  The clean, portable seam is a **plain function parameter**: each ported test is an
  exported `run*(t: Tracer): CheckResult`. The adapter is passed in. No registration
  ordering problem, works identically across backends. Matches the chosen
  "in-memory, mechanism provided by the target-language adapter" model.
- **`assert` is test-block-only.** It cannot appear in any function (confirmed by
  probe). So shared logic uses an own `Checker`/`CheckResult` (see
  `src/asserts.temper.md`); the in-repo `test(){}` block calls the `run*` fn then
  `assert(r.ok)`, and native adapters assert `result.ok` in their own runner.
- **Sibling files in `src/` are one module** — no `import("./x")` between them;
  exported symbols are directly in scope.
- **Generated JS boundary is ergonomic:** interface → extendable `Tracer` class;
  value types expose positional ctors + `.new({...})`; `CheckResult.ok` getter +
  `.summary()`. A native class `extends Tracer` and builds
  `CapturedSpan`/`CapturedLink` directly.
- **Attribute pass-through:** the Temper `Map<String,String>` handed to `addLink`
  is echoed back unchanged by the adapter; `Mapped.getOr` reads it on the Temper
  side without conversion.

## Temper idioms learned (for the porting waves)
- mutable field: `private var x: Int = 1;`  • nullable: `T?`  • unwrap: `(x as T) orelse panic()`
- no `match`; use `when (x) { is T -> … else -> … }`  • fatal: `panic()`  • recoverable: `throws Bubble` + `orelse`
- collections: `new ListBuilder<T>()`, `.add`, `[i]`, `.length`, `.toList()`;
  `new Map<K,V>([new Pair(k,v), …])`, `MapBuilder.set`, `.getOr(k, fallback)`, `.has`
- no `Listed.forEach` on builders here — index loops used.

## Files
- `src/tracer_api.temper.md` — `Tracer`, `CapturedSpan`, `CapturedLink`, query helpers.
- `src/asserts.temper.md` — `Checker` / `CheckResult`.
- `src/span_links.temper.md` — ported `run*` test logic.
- `src/fake_tracer.temper.md` — in-repo pure-Temper `Tracer` for validation.
- `src/system-tests-redux.temper.md` — in-repo `test(){}` validation block.
- `examples/js-adapter-demo/` — native JS adapter proving the boundary.

## Real dd-trace-js adapter — ✅ done
- `adapters/dd-trace-js/run.mjs` implements `Tracer` against a **live dd-trace-js**
  (v6.0.0-pre) tracer, reads real span objects + `_links` after finish, maps 64-bit
  ids to stable surrogates, and runs `runSpanWithAttachedLinks` → `PASS`. Broken
  adapter (dropped attrs) fails with 5 precise messages. Exercises the real link API
  + attribute flattening end-to-end.

## Still open (next, not blocking)
- `dd-trace-py` real adapter (same pattern).
- Optional: capture the **serialized** agent payload for wire-format fidelity
  (current capture reads in-memory span objects).
- `ADAPT(agent)` tests (telemetry/stats) still need a capture seam — unproven.
- Decide library packaging so adapters depend on the published Temper artifact
  (and exclude the in-repo `fake_tracer` / validation module from that artifact).
