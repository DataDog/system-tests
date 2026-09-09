from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import urllib.request

from python.runfiles import runfiles

from utils.parametric.process import PreparedProcessLaunch, ProcessContainer, ProcessLaunchSpec


def _runfile(path: str) -> Path:
    resolver = runfiles.Create()
    if resolver is None:
        raise RuntimeError("Bazel runfiles are unavailable")
    resolved = resolver.Rlocation(path)
    if resolved is None:
        raise FileNotFoundError(path)
    return Path(resolved)


def main() -> int:
    workspace = os.environ.get("TEST_WORKSPACE", "system_tests")
    output_directory = Path(os.environ["TEST_UNDECLARED_OUTPUTS_DIR"])
    launch = PreparedProcessLaunch.prepare(
        ProcessLaunchSpec.archive(
            _runfile(f"{workspace}/bazel/parametric/python_server_archive.zip"),
            entrypoint="bazel/parametric/python_server.py",
        )
    )
    container = ProcessContainer(
        name="python-archive-smoke",
        proot=_runfile("proot_static/usr/bin/proot.static"),
        launch=launch,
        environment={
            "DD_PATCH_MODULES": "fastapi:false,startlette:false",
            "DD_TRACE_AGENT_URL": "http://127.0.0.1:9",
            "DD_TRACE_OTEL_ENABLED": "true",
        },
        arguments=[],
        output_directory=output_directory,
    )
    try:
        port = container.assigned_port()
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/trace/agent/ensure_agent_info",
            timeout=30,
        ) as response:
            payload = json.load(response)
        if payload != {"ready": True}:
            raise RuntimeError(f"Unexpected Python server response: {payload!r}")
    finally:
        container.stop()
        container.remove(force=True)
        launch.cleanup()
    return 0


if __name__ == "__main__":
    sys.exit(main())
