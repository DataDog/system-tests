# dd-trace-py adapter

Runs the Temper conformance suite against a **live dd-trace-py** tracer — the
second real library (alongside dd-trace-js), proving the same compiled tests run
cross-library.

## Files
- `adapter.py` — implements the generated Python `Tracer` ABC against ddtrace
  (`tracer.start_span`, `span.set_tag/set_metric`, `span.context` baggage,
  `span.link_span`, `HTTPPropagator.inject/extract`, `config`). Captures spans
  from the live span objects after finish; trace ids are the low 64 bits.
- `run_one.py` — runs a single `ConformanceCase` by index.
- `run.py` — iterates `all_cases()` and runs each in its own subprocess with the
  case env applied (container-per-env model).

## Setup + run
```sh
python3 -m venv .venv-ddtrace
./.venv-ddtrace/bin/pip install ddtrace opentelemetry-api msgpack ddapm-test-agent
temper build -b py
./.venv-ddtrace/bin/python adapters/dd-trace-py/run.py
# -> 105/105 cases passed (dd-trace-py), 18 skipped
```
The generated Python lib + its Temper runtime are loaded from `temper.out/py`
via PYTHONPATH (set per-subprocess by run.py); no pip install of the Temper
packages is needed.

OTel is wired via ddtrace's OpenTelemetry bridge (`ddtrace.opentelemetry.
TracerProvider` + `opentelemetry-api`); all 5 otel_span cases pass on python,
including span-kind -> operation-name mapping (which ddtrace supports and nodejs
does not — matching upstream).

## Skips on this ddtrace (4.10.4) — genuine gaps, not faked
- **B3 single header (8: headers_b3 + b3single 128-bit):** ddtrace 4.10
  doesn't activate single-header B3 for the `"B3 single header"` style string
  (it uses `"b3"`); b3multi works.
- **otel_env_vars sample-rate / log-level (6):** ddtrace 4.10 doesn't expose the
  effective sample rate via a simple config attribute, and DD log level isn't a
  config field (upstream marks log-level python-`missing_feature`).
- **dup-header tracecontext (3) + baggage header extract (1):** the
  Listed<Pair>→dict carrier can't represent duplicate headers / the baggage
  header extract path (same limitation flagged for nodejs).

Each env-driven case was verified "real" (fails when its env is not applied).
