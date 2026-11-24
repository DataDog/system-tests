import os
from pathlib import Path
from types import SimpleNamespace
from typing import TextIO

from utils import pytest, scenarios
from utils.docker_fixtures._test_clients import _core

# the nightly failure (2026-11-23, php parametric)
TLS = 'ERROR: failed to solve: failed to do request: Head "https://registry-1.docker.io/v2/...": net/http: TLS handshake timeout'
BAD_GATEWAY = "#7 ERROR: failed to copy: unexpected status code https://registry-1.docker.io/v2/...: 502 Bad Gateway"
RUN_STEP = (
    '#9 1.2 ERROR: connection reset by peer\n#9 ERROR: process "/bin/sh -c pip install" did not complete successfully'
)
RECOVERED_THEN_COPY = '#6 1.2 ERROR: connection reset by peer, retrying\n#7 ERROR: "/missing.txt": not found'


@scenarios.test_the_test
@pytest.mark.parametrize(
    ("log", "transient"), [(TLS, True), (BAD_GATEWAY, True), (RUN_STEP, False), (RECOVERED_THEN_COPY, False)]
)
def test_is_transient_build_failure(log: str, *, transient: bool):
    assert _core._is_transient_build_failure(log) is transient  # noqa: SLF001


@scenarios.test_the_test
def test_build_is_retried_on_transient_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    outputs = [(1, TLS), (0, "done")]

    def fake_run(*_: object, stdout: TextIO, **__: object) -> SimpleNamespace:
        returncode, output = outputs.pop(0)
        os.write(stdout.fileno(), output.encode())
        return SimpleNamespace(returncode=returncode)

    monkeypatch.setattr(_core.subprocess, "run", fake_run)
    monkeypatch.setattr(_core.time, "sleep", lambda _: None)
    monkeypatch.setattr(_core.shutil, "which", lambda _: "docker")
    monkeypatch.setattr(_core, "mirror_enabled", lambda: False)
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM alpine\n")
    factory = _core.TestClientFactory("php", str(dockerfile), "tag", "name", {}, {})
    factory._image = SimpleNamespace(attrs={"Config": {"Cmd": ["run"]}})  # type: ignore[assignment]  # noqa: SLF001
    factory.configure(str(tmp_path))

    factory.build(github_token_file="")

    log = (tmp_path / "outputs" / "docker_build_log.log").read_text()
    assert log.count("docker build attempt") == 2
    assert log.index("TLS handshake timeout") < log.index("attempt 2/3") < log.index("done")
