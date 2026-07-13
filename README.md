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
(what's ported + skip fidelity), [GAPS.md](GAPS.md) (per-backend gap survey),
[FINDINGS.md](FINDINGS.md) (bugs the suite surfaced), [AUDIT.md](AUDIT.md)
(fidelity audit), and [PORTING_CHEATSHEET.md](PORTING_CHEATSHEET.md) (how to add tests).

**Status:** 243 conformance cases ported from `tests/parametric/`. Live runs
across **seven** backends: **dd-trace-js** (npm `dd-trace@5.107.0`) 216/243,
**dd-trace-py** (pip `ddtrace@4.10.4`) 236/243, **dd-trace-go** (`dd-trace-go/v2
@2.9.1`, native C-FFI) 212/243, **dd-trace-dotnet** (`Datadog.Trace@3.48.0`
under the CLR profiler, native C# backend) 209/243, **dd-trace-java**
(`dd-trace-java@1.63.2` under the javaagent, native Java backend) 218/243,
**dd-trace-ruby** (`datadog@2.37`, Ruby-hosted rust cdylib + Fiddle FFI) 193/243,
**dd-trace-php** (`ddtrace@1.21`, PHP-hosted rust cdylib + FFI) 205/243, and
**dd-trace-rust** (`dd-trace-rs`/`datadog-opentelemetry@0.5.0`, native Temper
crate — no FFI) 151/243. Remaining cases are per-library skips with genuine
reasons — see COVERAGE.md and each adapter's README. Exact counts shift with
library versions.

## Quick start
```sh
./setup.sh      # once: JS npm deps, Python venv + ddtrace + test-agent, Go 1.25, .NET restore
./run-all.sh    # build + run all four backends; prints one summary line each
./run-all.sh go # or run just one backend: js | py | go | dotnet
```
`setup.sh` needs these already on PATH: `temper`, `node`+`npm`, `python3`, the
`dotnet` SDK. It auto-installs everything else (incl. a Go 1.25 toolchain into
`~/toolchains/go1.25`, since dd-trace-go/v2 requires it). The sections below
spell out each backend by hand.

## Prerequisites
- `temper` (the Temper toolchain) on PATH
- Node.js (for the JS backend + dd-trace-js adapter)
- Python 3.11+ (for the Python backend + dd-trace-py adapter)
- npm-installed `dd-trace` + `@opentelemetry/api` for the JS adapter
  (`npm --prefix adapters/dd-trace-js install`)
- A Python venv with `ddtrace` + `opentelemetry-api` (for the py adapter)
- Go 1.25 (dd-trace-go/v2 requires it; the native C-FFI adapter build — see its README)
- .NET SDK (for the `csharp` backend + dd-trace-dotnet adapter; targets net6.0
  via RollForward, so a newer SDK works). The adapter runs under the Datadog CLR
  profiler from the `Datadog.Trace.Bundle` NuGet package (restored on build).
- Ruby 3.x + Rust/cargo (for the dd-trace-ruby adapter: the Temper suite compiles
  to a rust `cdylib` that a Ruby process loads via `Fiddle` and drives against
  the `datadog` gem — see its README).
- PHP 8.x with FFI + the `ddtrace` extension (for dd-trace-php: the same rust
  `cdylib`, loaded by a PHP process via FFI and driven against dd-trace-php — see
  its README). On macOS/arm64 `pecl install datadog_trace` needs the pcre2 header
  (`setup.sh` handles this).
- Maven + a JDK 17+ (for the `java` backend + dd-trace-java adapter). The
  adapter runs under `-javaagent:dd-java-agent.jar` (downloaded by setup.sh).

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

## 4. Against the real dd-trace-dotnet (native C# backend)
```sh
temper build -b csharp
dotnet build adapters/dd-trace-dotnet         # restores Datadog.Trace 3.48.0 + Datadog.Trace.Bundle
pkill -f ddapm-test-agent                     # the runner owns the agent
dotnet adapters/dd-trace-dotnet/bin/Debug/net6.0/conformance.dll
# -> NNN/NNN cases passed (dd-trace-dotnet), N skipped
```
Runs Datadog.Trace **v3** under the CLR profiler (the orchestrator loads the
native profiler from `Datadog.Trace.Bundle`), which the manual + OpenTelemetry
APIs require to produce real spans. See
[adapters/dd-trace-dotnet/README.md](adapters/dd-trace-dotnet/README.md).

## 5. Against the real dd-trace-java (native Java backend)
```sh
temper build -b java
for p in temper-core std system-tests-redux; do mvn -q -f temper.out/java/$p/pom.xml install -DskipTests -Dgpg.skip=true; done
mvn -q -f adapters/dd-trace-java/pom.xml package
/opt/homebrew/opt/openjdk@17/bin/java -cp adapters/dd-trace-java/target/conformance.jar ddtracejava.Main
# -> NNN/NNN cases passed (dd-trace-java), N skipped
```
dd-trace-java's manual API is a no-op without `-javaagent:dd-java-agent.jar`
(the OTel API is the manual surface the agent bridges). Needs a JDK 17+. See
[adapters/dd-trace-java/README.md](adapters/dd-trace-java/README.md).

## 6. Against the real dd-trace-rb (Ruby-hosted, rust cdylib via FFI)
```sh
bash adapters/dd-trace-ruby/build.sh           # temper build -b rust + patch + cargo build cdylib
/opt/homebrew/opt/ruby/bin/ruby adapters/dd-trace-ruby/run.rb
# -> NNN/NNN cases passed (dd-trace-ruby), N skipped
```
Unlike the others, Ruby has no Temper backend: the suite compiles to a rust
`cdylib`, a Ruby process `Fiddle`-loads it, and the suite's `Tracer` is a Ruby
callback backed by dd-trace-rb (in-process, no RPC). See
[adapters/dd-trace-ruby/README.md](adapters/dd-trace-ruby/README.md).

## 7. Against the real dd-trace-php (PHP-hosted, same rust cdylib via FFI)
```sh
bash adapters/dd-trace-ruby/build.sh           # shared cdylib (reused from ruby)
/opt/homebrew/opt/php/bin/php adapters/dd-trace-php/run.php
# -> NNN/NNN cases passed (dd-trace-php), N skipped
```
Same pattern as Ruby, different host: a PHP process (with the `ddtrace` Zend
extension) `FFI`-loads the **same** rust cdylib and drives it against
dd-trace-php's manual span API, plus the **OpenTelemetry API** (via
`open-telemetry/sdk` from composer + `DD_TRACE_OTEL_ENABLED=1`, which ddtrace
bridges to DD spans — the same OTel-API path used by the dotnet/java backends).
Second proof the host-in-the-target pattern generalizes to embedded languages.
See [adapters/dd-trace-php/README.md](adapters/dd-trace-php/README.md).

## 8. Against the real dd-trace-rs (native Temper crate, no FFI)
```sh
bash adapters/dd-trace-rust/build.sh           # temper build -b rust + cargo build --release
./.venv-ddtrace/bin/python adapters/dd-trace-rust/run.py
# -> 151/151 cases passed (dd-trace-rust), 92 skipped
```
The cleanest backend: Temper has a native rust target, so the suite is a rust
*lib crate* and the adapter is a plain rust binary that links it + drives real
dd-trace-rs in-process — no FFI, no cdylib. dd-trace-rs is very young
(OpenTelemetry-based, v0.5.0), so 60 of its cases are verified genuine gaps
(`KNOWN_RUST_DIFFS`: 128-bit `_dd.p.tid`, single-span sampling, OTEL_* config
mapping, SCI tags, tag-based sampling). See
[adapters/dd-trace-rust/README.md](adapters/dd-trace-rust/README.md).

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
adapters/dd-trace-go/      Go native C-FFI adapter (cshared.go + adapter.py)
adapters/dd-trace-dotnet/  C# adapter: Adapter.cs, Program.cs, DdTraceDotnet.csproj
adapters/dd-trace-java/    Java adapter: Adapter.java, Main.java, pom.xml
adapters/dd-trace-ruby/    Ruby adapter: adapter.rb, run.rb + rust cdylib shim (FFI)
adapters/dd-trace-php/     PHP adapter: adapter.php, run.php (FFI, reuses the shim)
adapters/dd-trace-rust/    Rust adapter: src/main.rs, run.py (native crate, no FFI)
examples/js-adapter-demo/  minimal hand-written adapter proving the boundary
temper.out/                generated per-backend output (gitignored)
```

## Adding a test
Read [PORTING_CHEATSHEET.md](PORTING_CHEATSHEET.md). In short: add an exported
`run<Name>(t: Tracer): CheckResult` to a `src/*.temper` file, register a
`ConformanceCase` in `src/cases.temper`, then build + run the adapters. Mark a
case `fakeSupported=false` when only a real tracer can judge it, and add a library
id to its `unsupported` list for genuine per-library gaps.
