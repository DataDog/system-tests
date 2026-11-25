from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

from utils import pytest
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
    # worktree binaries/. Since cwd is no longer the repo root, the child process needs REPO_ROOT
    # back on PYTHONPATH to resolve `utils` imports; the inherited PYTHONPATH is kept (not replaced)
    # because under nix it's also what makes third-party deps (e.g. pyyaml) importable.
    result = subprocess.run(
        [sys.executable, str(SCRIPT), SCENARIOS, "-l=golang", f"-w={weblog}"],
        check=False,
        capture_output=True,
        text=True,
        cwd=cwd,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join(filter(None, [str(REPO_ROOT), os.environ.get("PYTHONPATH")])),
        },
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

    @staticmethod
    def _flask_poc_images(tmp_path: Path, *, mirror: bool) -> list[str]:
        output = tmp_path / "compose.yaml"
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "DEFAULT", "-l=python", "-w=flask-poc", f"--output={output}"],
            check=False,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            env={
                **{key: value for key, value in os.environ.items() if key != "USE_IMAGE_MIRROR"},
                **({"USE_IMAGE_MIRROR": "1"} if mirror else {}),
                "PYTHONPATH": os.pathsep.join(filter(None, [str(REPO_ROOT), os.environ.get("PYTHONPATH")])),
            },
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout == "", "with --output, the compose file is not printed"
        return [service["image"] for service in yaml.safe_load(output.read_text())["services"].values()]

    def test_base_images_are_pulled_without_mirror(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """build.sh supplies them as named build contexts, from the docker daemon when it builds without the mirror."""
        from utils.base_images.base_image import base_image_contexts  # noqa: PLC0415

        dockerfile = REPO_ROOT / "utils/build/docker/python/flask-poc.Dockerfile"
        base_images = set(base_image_contexts(dockerfile.read_text()).values())
        assert base_images, "flask-poc is built from a base image: the test checks nothing otherwise"

        spec = importlib.util.spec_from_file_location("get_image_list", SCRIPT)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # no image exists locally, so none is filtered out
        monkeypatch.setattr(module, "get_docker_client", lambda: SimpleNamespace(images=SimpleNamespace(list=list)))
        monkeypatch.delenv("USE_IMAGE_MIRROR", raising=False)
        monkeypatch.chdir(REPO_ROOT)
        output = tmp_path / "compose.yaml"

        module.main(["DEFAULT"], library="python", weblog="flask-poc", output=str(output))

        images = {service["image"] for service in yaml.safe_load(output.read_text())["services"].values()}
        assert base_images <= images

    def test_mirrored_images_written_to_output(self, tmp_path: Path) -> None:
        """With USE_IMAGE_MIRROR, the images are listed under their mirror name, as the session pulls them.

        The GitLab run job pre-pulls them from the --output file: under their original name, the session would
        not find them locally, and pull them again. The images to build the weblog are not listed: the mirror
        BuildKit builder used by build.sh pulls them in its own store, not the docker daemon's.
        """
        from utils._context._image_mirror import _mapping  # noqa: PLC0415
        from utils._context.containers import dockerfile_image_list  # noqa: PLC0415
        from utils.base_images.base_image import base_image_contexts  # noqa: PLC0415

        images = self._flask_poc_images(tmp_path, mirror=True)

        mirrored = _mapping()
        assert not [image for image in images if image in mirrored], "an image with a mirror is listed under its name"
        dockerfile = REPO_ROOT / "utils/build/docker/python/flask-poc.Dockerfile"
        build_images = dockerfile_image_list(dockerfile) + list(base_image_contexts(dockerfile.read_text()).values())
        assert build_images, "flask-poc is built from images: the test checks nothing otherwise"
        for build_image in build_images:
            assert build_image not in images
            assert mirrored.get(build_image, build_image) not in images
