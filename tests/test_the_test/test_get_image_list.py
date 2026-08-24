from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from utils import scenarios


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "utils/scripts/get-image-list.py"
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


def _run_get_image_list(weblog: str, cwd: Path) -> str:
    # The proxy container constructors open binaries/<weblog>-image relative to the process cwd, so
    # running from `cwd` (a tmp dir) lets a test control the pointer without ever touching the real
    # worktree binaries/
    result = subprocess.run(
        [sys.executable, str(SCRIPT), SCENARIOS, "-l=golang", f"-w={weblog}"],
        check=False,
        capture_output=True,
        text=True,
        cwd=cwd,
    )

    assert result.returncode == 0, result.stderr

    return result.stdout


@scenarios.test_the_test
class Test_GetImageList:
    @pytest.mark.parametrize("weblog", sorted(GO_PROXY_POINTER_FILES))
    @pytest.mark.parametrize("pointer_present", [False, True], ids=["pointer_absent", "pointer_present"])
    def test_stdout_is_only_a_compose_document(self, weblog: str, pointer_present: bool, tmp_path: Path) -> None:  # noqa: FBT001
        """get-image-list.py stdout is a compose file, it must not carry anything else.

        A container constructor calling logger.stdout() would inject its message as an extra
        top-level key, and `docker compose` would then reject the generated compose.yaml. Both the
        present and absent pointer branches are exercised because only one of them reads the pointer
        file, and either could be the one that regresses.
        """

        pointer = tmp_path / GO_PROXY_POINTER_FILES[weblog]
        pointer.parent.mkdir(parents=True, exist_ok=True)
        if pointer_present:
            pointer.write_text("ghcr.io/datadog/system-tests/fake-processor:test-the-test\n", encoding="utf-8")

        stdout = _run_get_image_list(weblog, cwd=tmp_path)

        document = yaml.safe_load(stdout)

        assert isinstance(document, dict), f"stdout for weblog {weblog} is not a YAML mapping:\n{stdout}"
        assert sorted(document) == ["services"], (
            f"stdout for weblog {weblog} must only contain the services key. "
            f"A container constructor is writing on stdout instead of logging:\n{stdout}"
        )
        assert isinstance(document["services"], dict), f"services must be a mapping:\n{stdout}"
