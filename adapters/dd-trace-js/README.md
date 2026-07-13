# dd-trace-js adapter

Runs the Temper conformance suite against a **live dd-trace-js** tracer.

## Files
- `adapter.mjs` — implements the generated `Tracer` interface against dd-trace-js
  (in-memory capture by reading real span objects after `finish()`); exports
  `makeAdapter(tracer)` + `initTracer()`. dd-trace + @opentelemetry/api are
  resolved from this adapter's npm `node_modules` (see `package.json`).
- `run-one.mjs` — runs a single `ConformanceCase` by index against a tracer
  initialized under the current process env.
- `run.mjs` — iterates `allCases()` and spawns `run-one.mjs` **once per case with
  that case's env applied**, mirroring system-tests' container-per-env model and
  sidestepping dd-trace's process-global `init`.

## Run
```sh
npm --prefix adapters/dd-trace-js install   # once: dd-trace + @opentelemetry/api
temper build -b js                          # from repo root → temper.out/js
node adapters/dd-trace-js/run.mjs
# -> 120/120 cases passed (dd-trace-js), 3 skipped
```
dd-trace comes from npm (currently 5.107.0), like the Python adapter's
pip-installed ddtrace — no local checkout required.

## Notes
- Span/trace ids are the tracer's own decimal strings (match the header form),
  so no id remapping is needed.
- Env-parametrized cases (e.g. propagation style) get their env via the
  per-case subprocess; the case registry (`src/cases.temper`) is the single
  source of truth for name + env + run function.
- A productionized adapter depends on the **published** Temper library package
  and lives in the dd-trace-js repo's CI.
- Capture currently reads in-memory span objects; serialized-payload capture is
  a future fidelity enhancement.
