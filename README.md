# system-tests-redux

DataDog [system-tests](https://github.com/DataDog/system-tests) parametric tests,
re-implemented **once in [Temper](https://temperlang.dev/)** and run against each
`dd-trace-*` library through a thin per-language adapter — no per-language weblog
app, no shared HTTP server.

- **Test logic** lives in `src/*.temper`, written once, compiled to every
  Temper backend (JS, Python, …).
- **Each library** ships a small adapter implementing the generated `Tracer`
  interface against the real tracer and runs the compiled cases.
- A registry (`src/cases.temper`) is the single source of truth: each
  `ConformanceCase` = name + env + run function + `fakeSupported` + per-library
  `unsupported` list.

See [PLAN.md](PLAN.md), [EVALUATION.md](EVALUATION.md), [COVERAGE.md](COVERAGE.md)
(what's ported + skip fidelity), [AUDIT.md](AUDIT.md) (fidelity audit), and
[PORTING_CHEATSHEET.md](PORTING_CHEATSHEET.md) (how to add tests).

**Status:** 123 conformance cases ported from `tests/parametric/`. Live runs:
**dd-trace-js** (npm `dd-trace@5.107.0`) 120/123 and **dd-trace-py** (pip
`ddtrace@4.10.4`) 120/123, 3 skips each (genuine per-library gaps — see
COVERAGE.md). Exact counts shift with library versions.

## Prerequisites
- `temper` (the Temper toolchain) on PATH
- Node.js (for the JS backend + dd-trace-js adapter)
- Python 3.11+ (for the Python backend + dd-trace-py adapter)
- npm-installed `dd-trace` + `@opentelemetry/api` for the JS adapter
  (`npm --prefix adapters/dd-trace-js install`)
- A Python venv with `ddtrace` + `opentelemetry-api` (for the py adapter)

## 1. In-repo validation (fake tracer — fast, no real library)
Runs the `fakeSupported` cases through a pure-Temper `FakeTracer`, on each
backend. Proves the ported logic compiles to that language and is self-consistent.
```sh
temper test -b js     # JavaScript backend
temper test -b py     # Python backend
```
(The single reported test iterates all fake-supported cases with soft asserts;
it prints per-case detail on failure.)

## 2. Against the real dd-trace-js (npm)
```sh
npm --prefix adapters/dd-trace-js install           # once: dd-trace + @opentelemetry/api
temper build -b js                                  # generate temper.out/js
node adapters/dd-trace-js/run.mjs
# -> NNN/NNN cases passed (dd-trace-js), N skipped
```
Each case runs in its own subprocess with its env applied. The runner prints a
banner (node + dd-trace versions, generated-lib status) and `PASS`/`SKIP`/`FAIL`
per case.

## 3. Against the real dd-trace-py
```sh
python3 -m venv .venv-ddtrace
./.venv-ddtrace/bin/pip install ddtrace opentelemetry-api
temper build -b py
./.venv-ddtrace/bin/python adapters/dd-trace-py/run.py
# -> NNN/NNN cases passed (dd-trace-py), N skipped
```

## Handy variations
```sh
# only failures/skips + the summary line
node adapters/dd-trace-js/run.mjs 2>&1 | grep -E 'FAIL|SKIP|cases passed'

# list every case with its index
node -e 'import("./adapters/dd-trace-js/adapter.mjs").then(({lib})=>lib.allCases().forEach((c,i)=>console.log(i,c.name)))'

# run ONE case by index against the live tracer (uses current process env)
node adapters/dd-trace-js/run-one.mjs <index>
PYTHONPATH=adapters/dd-trace-py:temper.out/py/system-tests-redux:temper.out/py/temper-core:temper.out/py/std \
  ./.venv-ddtrace/bin/python adapters/dd-trace-py/run_one.py <index>

# "is it real?" check: run an env-driven case WITHOUT its env -> it must FAIL
node adapters/dd-trace-js/run-one.mjs <index>     # no env applied
```

## One-shot health check
```sh
temper build -b js && node adapters/dd-trace-js/run.mjs | tail -1
temper build -b py && ./.venv-ddtrace/bin/python adapters/dd-trace-py/run.py | tail -1
```

## Layout
```
src/                       Temper test logic (one file per family) + the registry
  config.temper.md           library config (literate; the Temper library marker)
  tracer_api.temper          the Tracer interface + captured shapes + helpers
  cases.temper               ConformanceCase registry (name, env, run, skips)
  fake_tracer.temper         pure-Temper Tracer for in-repo validation
  *.temper                   ported families (headers_*, span_*, otel_*, config_*, ...)
adapters/dd-trace-js/      JS adapter: adapter.mjs, run.mjs, run-one.mjs
adapters/dd-trace-py/      Python adapter: adapter.py, run.py, run_one.py
examples/js-adapter-demo/  minimal hand-written adapter proving the boundary
temper.out/                generated per-backend output (gitignored)
```

## Adding a test
Read [PORTING_CHEATSHEET.md](PORTING_CHEATSHEET.md). In short: add an exported
`run<Name>(t: Tracer): CheckResult` to a `src/*.temper` file, register a
`ConformanceCase` in `src/cases.temper`, then build + run the adapters. Mark a
case `fakeSupported=false` when only a real tracer can judge it, and add a library
id to its `unsupported` list for genuine per-library gaps.
