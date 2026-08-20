from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile

from python.runfiles import runfiles


def _runfile(path: str) -> str:
    resolver = runfiles.Create()
    if resolver is None:
        raise RuntimeError("Bazel runfiles are unavailable")
    resolved = resolver.Rlocation(path)
    if resolved is None:
        raise FileNotFoundError(path)
    return resolved


def main() -> int:
    workspace = os.environ.get("TEST_WORKSPACE", "system_tests")
    with tempfile.TemporaryDirectory(dir=os.environ.get("TEST_TMPDIR")) as temporary_directory:
        root = Path(temporary_directory)
        stable = root / "etc/datadog-agent/managed/datadog-agent/stable"
        logs = root / "parametric-tracer-logs"
        target = root / "opt/parametric/smoke"
        for directory in (stable, logs, root / "tmp", target.parent):
            directory.mkdir(parents=True, exist_ok=True)
        (stable / "smoke").write_text("stable-config-ok")
        target.touch()

        command = [
            _runfile("proot_static/usr/bin/proot.static"),
            "-0",
            "-r",
            str(root),
            "-b",
            f"{_runfile(f'{workspace}/bazel/parametric/proot_smoke_bin_/proot_smoke_bin')}:/opt/parametric/smoke",
            "-b",
            "/proc",
            "-w",
            "/tmp",  # noqa: S108 - this is the private sandbox's /tmp
            "/opt/parametric/smoke",
        ]
        stdout_path = root / "proot.stdout.log"
        stderr_path = root / "proot.stderr.log"
        timed_out = False
        with stdout_path.open("w") as stdout, stderr_path.open("w") as stderr:
            process = subprocess.Popen(
                command,
                text=True,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
            )
            try:
                returncode = process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(process.pid, signal.SIGKILL)
                returncode = process.wait()

        stdout_text = stdout_path.read_text()
        stderr_text = stderr_path.read_text()
        output_directory = Path(os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR", temporary_directory))
        output_directory.mkdir(parents=True, exist_ok=True)
        (output_directory / "proot-smoke.stdout.log").write_text(stdout_text)
        (output_directory / "proot-smoke.stderr.log").write_text(stderr_text)
        if timed_out:
            raise RuntimeError(f"PRoot smoke timed out:\n{stderr_text}")
        if returncode != 0:
            raise RuntimeError(f"PRoot smoke failed ({returncode}):\n{stderr_text}")
        if stdout_text != "proot-smoke-ok":
            raise AssertionError(f"Unexpected smoke output: {stdout_text!r}")
        if (logs / "smoke.log").read_text() != "stable-config-ok":
            raise AssertionError("PRoot did not preserve the sandbox trace-log write")
    return 0


if __name__ == "__main__":
    sys.exit(main())
