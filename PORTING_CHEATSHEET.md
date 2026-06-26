# Temper porting cheatsheet (for conformance test authors)

You are writing ONE new file `src/<family>.temper` containing exported
`run*` functions that port parametric tests. Follow these rules exactly — they
encode hard-won Temper idioms. Do NOT edit any other file. Do NOT run a build.

## File / module rules
- All files in `src/` are ONE module. **Only `export`ed top-level symbols are
  visible from other files.** Non-exported `let` is file-local.
- So: use the shared exports below, and define any small parser helpers you need
  as **file-local `let`** (give them a family-unique name to be safe, e.g.
  `b3TraceId`, not `traceId`).
- Plain Temper source (`.temper`): write code directly; use `//` line comments
  for prose/section headings. See existing `src/headers_b3.temper`.

## Shared exports you may call (already defined elsewhere — do NOT redefine)
- Types: `Tracer`, `CapturedSpan`, `CapturedLink`, `Checker`, `CheckResult`, `Pair`.
- `CapturedSpan` fields: `.traceId .spanId .parentId .name .service .resource .spanType .meta .metrics .links` (ids are **decimal Strings**; `"0"` = none; `meta: Mapped<String,String>`, `metrics: Mapped<String,Float64>`).
- `CapturedLink` fields: `.spanId .traceId .traceIdHigh .attributes`.
- Tracer methods: `startSpan(name, parentId, service="", resource="", spanType="") -> CapturedSpan`, `finishSpan(id)`, `setMeta(id,k,v)`, `setMetric(id,k,Float64)`, `addLink(id, linkToId, attrs)`, `extractHeaders(Listed<Pair>) -> String`, `injectHeaders(id) -> Mapped<String,String>`, `flush()`, `capturedSpans() -> Listed<CapturedSpan>`.
- Query: `findSpan(spans, id)`, `findOnlySpan(spans)`, `spanHasNoParent(span)`, `traceSpans(spans, traceId)`.
- Header helper: `makeChildSpanAndGetHeaders(t, Listed<Pair<String,String>>) -> Mapped<String,String>` (extract → child span → inject → returns injected headers; the child is then in `t.capturedSpans()`).
- Hex (from hex module): `strLen(s) -> Int`, `hexLow64ToDecimal(hex) -> String` (low 16 hex chars → decimal), `hexToDecimal(hex) -> String`.

## Checker (assertions) — `assert` is ONLY allowed in `test` blocks, so use this
```
let c = new Checker();
c.isTrue(cond, "msg");
c.eqInt(actualInt, expectedInt, "msg");
c.eqStr(actualStr, expectedStr, "msg");
c.eqFloat(actualF, expectedF, "msg");
return c.result()   // last expression; no `return` keyword needed
```
Every `run*` is: `export let runX(t: Tracer): CheckResult { let c = new Checker(); ...; c.result() }`

## Language idioms (these bite)
- Mutable local: `var x = 1;`  immutable: `let x = 1;`  Class ctor params are immutable.
- Class mutable field: `private var n: Int = 1;`  field with default: `public links: ListBuilder<CapturedLink> = new ListBuilder<CapturedLink>();`
- Nullable type `T?`; unwrap with `(x as T) orelse panic()`. Avoid `match`; there is no `match`. `when (x) { is T -> ...; else -> ... }` exists but is finicky — prefer plain `if`.
- Fatal: `panic()`. Recoverable: declare `... throws Bubble` and use `orelse`.
- `if` is an expression: `let v = if (cond) { "a" } else { "b" };`
- String interpolation: `"${expr}"`.
- Float literal needs a dot: `1.0`, `0.0`, `-1.0`. Int64 from int: `(123).toInt64()`.

## Collections
- `new ListBuilder<T>()`, `.add(x)`, `lb[i]`, `.length`, `.toList()`.
- Typed empty list: `new ListBuilder<T>().toList()`  (NEVER `[] as List<T>` — that fails).
- List literal with elements is fine: `[pr("a","b"), pr("c","d")]`.
- `new Map<K,V>([new Pair(k,v), ...])`; `MapBuilder` has `.set(k,v)`; both are `Mapped` with `.getOr(k, fallback)`, `.has(k)`, `.length`, `.get(k)` (throws — prefer getOr).

## String ops
- `s.split(sep) -> List<String>` (e.g. `"a-b-c".split("-")` → `["a","b","c"]`, index with `[0]`).
- Length: use shared `strLen(s)` (String has no `.length`).
- Substring: `s.slice(begin, end)` where indices are StringIndex: `String.begin`, `s.end`, `s.step(idx, n)` (n may be negative). Last 16 chars: `s.slice(s.step(s.end, -16), s.end)`.
- `s.toInt64(16) orelse (0).toInt64()` for hex→Int64; `"${int64val}"` → decimal string.
- Substring-contains trick: `haystack.split(needle).length > 1`.
- startsWith helper (define file-local):
  `let xStartsWith(s: String, p: String): Boolean { let pl = strLen(p); if (strLen(s) < pl) { return false; } s.slice(String.begin, s.step(String.begin, pl)) == p }`

## Building input header pairs
```
let pr(k: String, v: String): Pair<String, String> { new Pair(k, v) }   // file-local
let headers = [pr("x-datadog-trace-id", "123"), pr("x-datadog-parent-id", "456")];
let injected = makeChildSpanAndGetHeaders(t, headers);   // Mapped<String,String>
t.flush();
let span = findOnlySpan(t.capturedSpans());
```

## Common span-tag keys (use exact strings)
`_sampling_priority_v1` (metric), `_dd.origin` (meta), `_dd.p.dm` (meta),
`_dd.p.tid` (meta), `_dd.span_sampling.rule_rate` / `.mechanism` / `.max_per_second` (metrics),
`_dd.rule_psr` (metric).

## What NOT to do
- Don't use builtin `assert` outside a `test` block (it won't compile).
- Don't redefine exported names (`strLen`, `findSpan`, `Checker`, ...).
- Don't edit `cases.temper`, the adapter, or other family files.
- Don't try to compare 64-bit/128-bit ids as integers — compare decimal strings, or use `hexLow64ToDecimal`/`hexToDecimal` then `c.eqStr(...)`.

## Authoring target
Faithfully translate each test's documented assertions from the spec. The spec's
expected values are ground truth (they pass against real tracers). For
"present"/"absent" use `out.has(k)` / `!out.has(k)`. For "!= X" use
`c.isTrue(a != b, "...")`.
