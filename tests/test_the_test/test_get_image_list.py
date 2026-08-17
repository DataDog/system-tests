from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest
import yaml

from utils import scenarios


if TYPE_CHECKING:
    from collections.abc import Iterator


SCRIPT = Path("utils/scripts/get-image-list.py")
SCENARIOS = "APPSEC_BLOCKING,DEFAULT"

# .github/actions/pull_images redirects the script's stdout into compose.yaml, then feeds that file
# to `docker compose`. Container objects are built during that call, so anything a container
# constructor writes on stdout becomes part of the compose document.
#
# The go proxy weblogs are the ones exposed to this: each of them resolves its processor image from
# an optional pointer file in binaries/, a branch that has historically been tempting to report on
# stdout.
GO_PROXY_POINTER_FILES = {
    "apim": Path("binaries/golang-apim-callout-image"),
    "envoy": Path("binaries/golang-service-extensions-callout-image"),
    "haproxy": Path("binaries/golang-haproxy-spoa-image"),
}


@contextmanager
def _pointer_file(path: Path, *, present: bool) -> Iterator[None]:
    """Force the presence or the absence of a binaries/ image pointer file.

    A pointer file already sitting there is a local build artifact: move it aside and put it back,
    so both states can be tested whatever the checkout looks like.
    """

    backup = path.parent / f"{path.name}.test_the_test_backup"
    if backup.is_file():
        path.unlink(missing_ok=True)
        backup.rename(path)

    existed = path.is_file()

    if existed:
        path.rename(backup)

    try:
        if present:
            path.write_text("ghcr.io/datadog/system-tests/fake-processor:test-the-test\n", encoding="utf-8")

        yield
    finally:
        path.unlink(missing_ok=True)

        if existed:
            backup.rename(path)


def _run_get_image_list(weblog: str) -> str:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), SCENARIOS, "-l=golang", f"-w={weblog}"],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "."},
    )

    assert result.returncode == 0, result.stderr

    return result.stdout


@scenarios.test_the_test
class Test_GetImageList:
    def test_pointer_file_recovers_interrupted_present_state(self, tmp_path: Path) -> None:
        pointer = tmp_path / "processor-image"
        backup = tmp_path / "processor-image.test_the_test_backup"
        pointer.write_text("fake-test-pointer\n", encoding="utf-8")
        backup.write_text("original-pointer\n", encoding="utf-8")

        with _pointer_file(pointer, present=False):
            assert not pointer.exists()

        assert pointer.read_text(encoding="utf-8") == "original-pointer\n"
        assert not backup.exists()

    @pytest.mark.parametrize("weblog", sorted(GO_PROXY_POINTER_FILES))
    @pytest.mark.parametrize("pointer_present", [False, True], ids=["pointer_absent", "pointer_present"])
    def test_stdout_is_only_a_compose_document(self, weblog: str, pointer_present: bool):  # noqa: FBT001
        """get-image-list.py stdout is a compose file, it must not carry anything else.

        A container constructor calling logger.stdout() would inject its message as an extra
        top-level key, and `docker compose` would then reject the generated compose.yaml.
        """

        with _pointer_file(GO_PROXY_POINTER_FILES[weblog], present=pointer_present):
            stdout = _run_get_image_list(weblog)

        document = yaml.safe_load(stdout)

        assert isinstance(document, dict), f"stdout for weblog {weblog} is not a YAML mapping:\n{stdout}"
        assert sorted(document) == ["services"], (
            f"stdout for weblog {weblog} must only contain the services key. "
            f"A container constructor is writing on stdout instead of logging:\n{stdout}"
        )
        assert isinstance(document["services"], dict), f"services must be a mapping:\n{stdout}"
