# Plan: Port web-app-free system-tests to Temper

## Goal

1. Find DataDog/system-tests cases that need **no language-specific weblog web app**, being aggressive — rewriting a test wholesale is fine if its *intent* (the behavior under test) is preserved.
2. Re-implement those tests **once in Temper**, living in this repo, compiled to each target language. Each `dd-trace-*` library writes thin **adapter** code so the compiled tests run against it.

---

## Findings (recon already done)

### system-tests taxonomy
- `tests/` has ~196 test files. **142 require a weblog** (full HTTP app per language). **54 do not.**
- The non-weblog suite that matters is **`tests/parametric/`**: ~30 files, **371 test functions**, zero weblog dependency.
- Remaining non-weblog files are infra (k8s lib-injection, ssi, onboarding) — out of scope.

### How parametric tests already work (the precedent)
- Shared Python pytest cases drive a **language-agnostic RPC interface** (~40 methods: span start/finish, set_meta/metric/error, baggage, links, events, headers inject/extract, flush, OTel span API, config).
- Each language ships a tiny **HTTP server** implementing that interface against its tracer — this server *is* today's adapter. Servers exist for: `nodejs, python, java, dotnet, golang, ruby, php, cpp` (no rust).
- Tests assert against a **dd-apm-test-agent** that collects emitted traces; queries via `wait_for_num_traces(n)` then structural asserts on the trace JSON.

This RPC interface is the seam we exploit: it is already a clean abstraction of "tracer under test."

### Temper capabilities (confirmed)
- `interface` / `class extends`, `test("name"){ assert(...) }` macro. Tests are co-located, **extracted per-backend automatically** and translated to native runners (MSTest, JUnit, pytest, node test, etc.). Soft assertions built in.
- Backends in docs: `csharp, java, java8, js, lua, mypyc, python, rust`. `go` WIP (~12.5% suite passing). `cpp` backend dir exists, not in docs (maturity uncertain).
- `@connected(...)` binds Temper symbols to native runtime impls but is **compiler-internal** — not the user-facing injection path. User-facing path = interface + dependency injection.

### Temper-backend ↔ dd-trace coverage
| dd-trace lib | parametric server today | Temper backend | Pilot tier |
|---|---|---|---|
| dd-trace-js (Node) | yes | js (mature) | **Tier 1** |
| dd-trace-py | yes | python (mature) | **Tier 1** |
| dd-trace-java | yes | java (mature) | **Tier 1** |
| dd-trace-dotnet | yes | csharp (mature) | **Tier 1** |
| dd-trace-rs / php-via-libdatadog | no | rust (mature) | Tier 2 |
| dd-trace-go | yes | go (WIP) | Tier 2 (blocked on Go backend) |
| dd-trace-cpp | yes | cpp (uncertain) | Tier 3 |
| dd-trace-rb (Ruby) | yes | **none** | Excluded — keep Python harness |
| dd-trace-php (pure PHP) | yes | **none** | Excluded — keep Python harness |

**Aggressive verdict:** the entire `tests/parametric/` suite (371 funcs) is portable in theory. Ruby/PHP can't consume Temper output, so they stay on the existing Python harness (dual-track, not a blocker).

---

## Architecture (target design)

```
this repo (Temper library: "ddtrace-conformance")
├── src/
│   ├── tracer_api.temper        # interface Tracer, Span, OtelSpan  (the RPC surface, typed)
│   ├── test_agent.temper        # interface TestAgent + trace/span query helpers
│   ├── harness.temper           # registerAdapter()/currentAdapter() injection seam
│   └── tests/
│       ├── headers_datadog.temper.md
│       ├── span_links.temper.md
│       └── ...                  # one file per ported parametric module, with test(){} blocks
└── temper.out/<backend>/...     # generated native test projects

each dd-trace-* repo
└── system-tests-temper-adapter/
    ├── depends on generated "ddtrace-conformance" lib for that backend
    ├── implements Tracer/Span/OtelSpan/TestAgent against the real tracer
    ├── calls registerAdapter(impl) in test setup
    └── runs the extracted native tests in CI
```

Key seam: a Temper `interface Tracer` (+ `Span`, `OtelSpan`, `TestAgent`). Test bodies are pure Temper calling those interfaces and asserting on returned trace structures. The concrete impl is **injected** by each library's adapter before tests run. No HTTP server, no weblog — the adapter is in-process native code.

Open design question to resolve in the spike: **how the adapter registers itself per backend.** Candidates: (a) a settable module-level `var currentAdapter` the native harness assigns in test setup; (b) a `@connected` factory bound per backend; (c) Temper test fixtures if available. (a) is most portable and is the working assumption.

---

## Phases

### Phase 0 — Decisions & repo skeleton  _(small)_
- **DECIDED:** trace-assertion model = **in-memory capture, mechanism provided by each target-language adapter.** No network from Temper. Adapter captures emitted spans (and later telemetry/stats) and hands them back through the interface.
- **DECIDED:** **narrow spike** — js + py only before scaling (not full Tier 1).
- `temper init` this repo; set library config + per-backend output.

### Phase 1 — Evaluation deliverable  _(DONE)_
- See **`EVALUATION.md`**: all 371 parametric tests classified → PORT (~290), PORT(config) (~26), ADAPT(agent) (~17), DEFER(rc) (~24), KEEP(native) (~18). ~85% portable in early waves. Wave ordering defined there.

### Phase 2 — Define shared Temper interfaces  _(medium)_
- Translate the ~40-method RPC surface into typed Temper interfaces (`Tracer`, `Span`, `OtelSpan`, `TestAgent`, value types for SpanContext/Link/Event/config).
- Build trace-query helpers in Temper (`findTrace`, `findSpan`, `findRootSpan`, etc.) ported from `utils/parametric/spec/trace.py`.
- Build the `harness.temper` injection seam.

### Phase 3 — Adapter-injection spike  _(DONE — see `SPIKE.md`)_
- Ported `test_span_with_attached_links`; green on `temper test -b js` **and** `-b py`; a native JS adapter (no Temper at runtime) drove the compiled test to PASS; a broken adapter fails with precise messages.
- **Injection mechanism resolved:** plain function parameter — `run*(t: Tracer): CheckResult` — not a global registry. No ordering risk; uniform across backends.
- **`assert` is test-block-only** → shared logic uses own `Checker`/`CheckResult`.
- Remaining: wire a *real* dd-trace-js/py adapter against the live tracer (folded into Phase 5).

### Phase 4 — Port pure-logic tests  _(IN PROGRESS)_
- Port the "pure-logic" bucket from Phase 1, file by file, with exported `run*(t: Tracer): CheckResult` functions mirroring intent.
- Ported so far (green on js+py + real dd-trace-js adapter): see `COVERAGE.md` (7 functions: span_links attached, tracer top-level attrs, headers_datadog D001–D005). Ids are now decimal strings; interface covers spans, service/resource/type, meta/metrics, links + flattened attrs, and Datadog header extract/inject + propagation.
- TODO: per-library missing-feature/skip mechanism (not yet needed); remaining Wave-1 files (span_sampling, sampling_span_tags, partial_flushing, more span_links/headers families).
- Coverage ledger lives in `COVERAGE.md`.

### Phase 5 — dd-trace adapters (Tier 1)  _(large, parallel per lib)_
- For js / py / java / dotnet: implement the adapter package, wire into each repo's CI to run the extracted native tests.
- Each repo owns its adapter (mirrors today's "each lang owns its parametric server").
- Provide an adapter conformance checklist + a reference adapter (the spike's js one).

### Phase 6 — Agent-dependent + Tier 2/3  _(medium)_
- Add `TestAgent` interface support if real-agent assertions are needed; port telemetry/stats/dynamic-config tests.
- Bring up rust adapter (Tier 2). Re-evaluate go once Temper Go backend matures; cpp last.

### Phase 7 — Dual-track & migration  _(small/ongoing)_
- Ruby/PHP stay on the Python parametric harness; document the split.
- Decide deprecation policy: as a Temper test reaches parity across Tier-1 langs, retire the corresponding Python parametric test (or keep Python driving Ruby/PHP only).

---

## Risks / unknowns (to verify, not assume)
- **Injection mechanism** across all backends — *the* critical spike (Phase 3). Working assumption: module-level settable adapter var. Not yet proven.
- **Trace-assertion source** — in-memory capture vs real test-agent. Proposing in-memory; needs sign-off.
- **Temper expressiveness** for some assertions (hex/bitwise trace-id math, JSON-ish nested attribute flattening like `array.0`). Likely fine, verify in spike.
- **Go/C++ backend maturity** gates Tier 2/3 — not on critical path.
- **Process-level tests** (crash/flare/discovery) may never be pure-Temper; plan keeps them native-assisted or on Python.
- This `system-tests-redux` working copy is empty + not yet a VCS repo; Phase 0 must `temper init` and choose VCS.

## Suggested first concrete step
Phase 3 spike on `span_links` × `js`, because it exercises spans, links, attribute flattening, and trace-structure assertions in one small test — a good stress test of the whole seam before committing to 371 ports.
