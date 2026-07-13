"""Conformance runner for dd-trace-py.

  temper build -b py
  ./.venv-ddtrace/bin/python adapters/dd-trace-py/run.py

Iterates the ConformanceCase registry and runs each case in its own subprocess
with the case's env applied (mirrors system-tests' container-per-env model and
sidesteps ddtrace's process-global init).
"""
import os
import socket
import subprocess
import sys
import time
import urllib.request

LIBRARY = "python"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PYOUT = os.path.join(REPO, "temper.out", "py")
PYPATH = os.pathsep.join([
    HERE,
    os.path.join(PYOUT, "system-tests-redux"),
    os.path.join(PYOUT, "temper-core"),
    os.path.join(PYOUT, "std"),
])

from adapter import make_adapter  # noqa: E402  (also validates import path)
from system_tests_redux.system_tests_redux import all_cases  # noqa: E402

cases = all_cases()
print("— dd-trace-py conformance runner —")
print(f"python:   {sys.version.split()[0]} ({sys.executable})")
import ddtrace  # noqa: E402
print(f"ddtrace:  {ddtrace.__version__}")
print(f"cases:    {len(cases)}\n")

# Start a real ddapm-test-agent if any case needs the wire (delivered traces / stats).
_agent_proc = None
_agent_url = None


def _needs_agent(c):
    return bool(getattr(c, "needs_agent", False))


def _agent_get(path):
    try:
        return urllib.request.urlopen(_agent_url + path, timeout=3).read()
    except Exception:
        return None


if any(_needs_agent(c) for c in cases):
    _s = socket.socket(); _s.bind(("127.0.0.1", 0)); _agent_port = _s.getsockname()[1]; _s.close()
    _agent_url = f"http://127.0.0.1:{_agent_port}"
    _agent_proc = subprocess.Popen(
        [os.path.join(os.path.dirname(sys.executable), "ddapm-test-agent"), "--port", str(_agent_port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        if _agent_get("/info") is not None:
            break
        time.sleep(0.2)

failed = 0
skipped = 0
for i, case in enumerate(cases):
    if LIBRARY in list(case.unsupported):
        print(f"SKIP {case.name} (unsupported on {LIBRARY})")
        skipped += 1
        continue
    env = dict(os.environ)
    env["PYTHONPATH"] = PYPATH
    if _needs_agent(case) and _agent_url:
        env["DD_TRACE_AGENT_URL"] = _agent_url
        _agent_get("/test/session/clear")
    for k in case.env.keys():
        env[k] = case.env[k]
    # ddtrace names the single-header B3 style "b3" (the canonical system-tests
    # name is "B3 single header"); translate it for the propagation-style vars.
    for sk in ("DD_TRACE_PROPAGATION_STYLE", "DD_TRACE_PROPAGATION_STYLE_EXTRACT", "DD_TRACE_PROPAGATION_STYLE_INJECT"):
        if sk in env:
            env[sk] = env[sk].replace("B3 single header", "b3")
    res = subprocess.run(
        [sys.executable, os.path.join(HERE, "run_one.py"), str(i)],
        env=env, capture_output=True, text=True,
    )
    sys.stdout.write(res.stdout)
    if res.returncode != 0 and not res.stdout.strip():
        sys.stderr.write(res.stderr)
    if res.returncode != 0:
        failed += 1

if _agent_proc is not None:
    _agent_proc.terminate()

ran = len(cases) - skipped
print(f"\n{ran - failed}/{ran} cases passed (dd-trace-py)" + (f", {skipped} skipped" if skipped else ""))
sys.exit(1 if failed else 0)
