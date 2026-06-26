"""Run a single conformance case by index against dd-trace-py.

The case env is applied by the parent runner (run.py) via the subprocess env.
Prints one PASS/FAIL line; exits non-zero on failure.
"""
import os
import sys

# Remote-config cases need ddtrace's product bootstrap (which starts the RC
# poller); a plain `import ddtrace` leaves it stopped.
if os.environ.get("DD_REMOTE_CONFIGURATION_ENABLED") == "true":
    import ddtrace.auto  # noqa: F401

from adapter import make_adapter  # noqa: E402
from system_tests_redux.system_tests_redux import all_cases  # noqa: E402

index = int(sys.argv[1])
cases = all_cases()
if index < 0 or index >= len(cases):
    print(f"no case at index {index}", file=sys.stderr)
    sys.exit(2)
case = cases[index]

try:
    result = case.run(make_adapter())
except Exception as e:  # adapter raised (e.g. unsupported op) -> FAIL
    print(f"FAIL {case.name}:\n  exception: {e!r}")
    sys.exit(1)

if result.ok:
    print(f"PASS {case.name}")
    sys.exit(0)
else:
    print(f"FAIL {case.name}:\n{result.summary()}")
    sys.exit(1)
