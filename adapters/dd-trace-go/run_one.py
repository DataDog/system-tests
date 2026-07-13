"""Run one conformance case by index against dd-trace-go (via ctypes FFI).

The case env (DD_* vars, including DD_TRACE_SAMPLING_RULES and the
DD_TRACE_STATS_COMPUTATION_ENABLED=false sampling fix) must be present in the
real *process* environment before the c-shared dylib loads: dd-trace-go's Go
runtime snapshots the environment at load time, so mutating os.environ from
Python afterwards has no effect. run.py supplies that env via the subprocess
`env=` argument. To run a single case standalone for isolation, export the
case env (and DD_TRACE_STATS_COMPUTATION_ENABLED=false for sampling cases) in
the shell before invoking this script. The schema of DD_TRACE_SAMPLING_RULES /
DD_SPAN_SAMPLING_RULES is unchanged between v1 and v2 — see README.
"""
import os
import sys

from adapter import make_adapter  # noqa: E402
from system_tests_redux.system_tests_redux import all_cases  # noqa: E402

index = int(sys.argv[1])
case = all_cases()[index]
# When run.py marks this as a known dd-trace-go difference, a genuine failure is
# downgraded to a documented skip -- but a case that unexpectedly PASSES still
# reports PASS, so the KNOWN_GO_DIFFS list can't hide a regression-to-green.
known_diff = os.environ.get("GO_KNOWN_DIFF") == "1"
_diff_msg = f"SKIP {case.name} (known dd-trace-go v2.9.1 difference)"
try:
    result = case.run(make_adapter())
except NotImplementedError:
    print(f"SKIP {case.name} (unsupported on golang)")
    sys.exit(2)
except Exception as e:
    if known_diff:
        print(_diff_msg)
        sys.exit(2)
    print(f"FAIL {case.name}:\n  exception: {e!r}")
    sys.exit(1)
if result.ok:
    print(f"PASS {case.name}")
    sys.exit(0)
if known_diff:
    print(_diff_msg)
    sys.exit(2)
print(f"FAIL {case.name}:\n{result.summary()}")
sys.exit(1)
