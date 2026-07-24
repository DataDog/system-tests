import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from rebuildr import ImageHandle, Project
from rebuildr.project import CacheLocation

import utils.docker_ssi.image_builder as image_builder_module
from utils.docker_ssi.image_builder import DockerSSIImageBuilder, DockerSSIImageError


pytestmark = pytest.mark.scenario("TEST_THE_TEST")
_ROOT = Path(__file__).parents[2]
_BASE_DIGEST = "sha256:" + "1" * 64


def _fixture(root: Path) -> None:
    for directory in (
        "utils/build/ssi/base",
        "utils/build/ssi/python",
        "lib-injection/build/docker/python",
    ):
        shutil.copytree(_ROOT / directory, root / directory)


def _builder(
    root: Path,
    *,
    arch: str = "linux/amd64",
    runtime: str | None = "3.12.7",
    push: bool = False,
    library_version: str | None = None,
    injector_version: str | None = None,
) -> DockerSSIImageBuilder:
    return DockerSSIImageBuilder(
        str(root / "logs"),
        "py-app",
        "ubuntu:24.04",
        "python",
        arch,
        runtime,
        push,
        "prod",
        library_version,
        injector_version,
        root_dir=root,
    )


def _project(
    builder: DockerSSIImageBuilder,
    root: Path,
    *,
    digest: str = _BASE_DIGEST,
    installer: bytes = b"installer",
) -> Project:
    (root / "installer.sh").write_bytes(installer)
    return builder._load_project(f"ubuntu@{digest}", "installer.sh")  # noqa: SLF001


def _images(project: Project) -> dict[str, ImageHandle]:
    return {handle.name: handle for handle in project.select(["ssi-installer", "weblog"])}


def test_rebuildr_graph_links_every_image(tmp_path: Path) -> None:
    _fixture(tmp_path)
    images = _images(_project(_builder(tmp_path), tmp_path))
    installer, weblog = images["ssi-installer"], images["weblog"]
    ssi = weblog.image_refs["ssi-image"]

    assert set(installer.image_refs) == {"cached-base"}
    assert installer.definition.tag == "latest"
    assert (
        installer.metadata["manifest"]["image_references"][0]["source_digest"]
        == installer.image_refs["cached-base"].source_digest
    )
    # The per-run images stay out of the content cache, and the SSI runtime is the
    # single graph edge between the weblog and the reusable installer.
    assert weblog.definition.repository == "weblog-injection"
    assert weblog.definition.content_tag is False
    assert ssi.definition.content_tag is False
    assert ssi.image_refs["installer-image"] is installer


def test_reusable_images_only_change_with_their_own_inputs(tmp_path: Path) -> None:
    _fixture(tmp_path)
    installer = _images(_project(_builder(tmp_path), tmp_path))["ssi-installer"]

    changed = [
        _project(_builder(tmp_path), tmp_path, digest="sha256:" + "2" * 64),
        _project(_builder(tmp_path, arch="linux/arm64"), tmp_path),
        _project(_builder(tmp_path, runtime="3.11.10"), tmp_path),
        _project(_builder(tmp_path), tmp_path, installer=b"changed"),
    ]
    (tmp_path / "utils/build/ssi/base/base_lang.Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    changed.append(_project(_builder(tmp_path), tmp_path))
    assert all(_images(project)["ssi-installer"].source_digest != installer.source_digest for project in changed)


@pytest.mark.parametrize(
    ("binaries", "installer", "expected"),
    [
        ({}, ".installer.sh", []),
        ({"custom-tracer.whl": b"wheel"}, ".installer.sh", ["custom-tracer.whl"]),
        ({}, "utils/build/ssi/base/binaries/install_script_agent7.sh", []),
        (
            {"custom-tracer.whl": b"wheel"},
            "utils/build/ssi/base/binaries/install_script_agent7.sh",
            ["custom-tracer.whl"],
        ),
    ],
    ids=["downloaded", "downloaded-with-artifacts", "local-copy", "local-copy-with-artifacts"],
)
def test_custom_binaries_reach_the_ssi_image(
    tmp_path: Path, binaries: dict[str, bytes], installer: str, expected: list[str]
) -> None:
    _fixture(tmp_path)
    directory = tmp_path / "utils/build/ssi/base/binaries"
    if binaries or installer.startswith("utils/"):
        directory.mkdir()
    for name, content in binaries.items():
        (directory / name).write_bytes(content)
    if installer.startswith("utils/"):
        (tmp_path / installer).write_bytes(b"local installer")
    else:
        (tmp_path / installer).write_bytes(b"downloaded installer")

    project = _builder(tmp_path)._load_project(f"ubuntu@{_BASE_DIGEST}", installer)  # noqa: SLF001
    ssi = project.image("weblog").image_refs["ssi-image"]

    # The agent installer is always present exactly once, whatever its source.
    assert sorted(entry.target_path.as_posix() for entry in ssi.inputs.files) == [
        *sorted(f"base/binaries/{name}" for name in [*expected, "install_script_agent7.sh"]),
        "base/install_script_ssi.sh",
    ]


def test_versions_change_only_the_per_run_images(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fixture(tmp_path)
    monkeypatch.setattr(image_builder_module.uuid, "uuid4", lambda: SimpleNamespace(hex="nonce"))
    first = _images(_project(_builder(tmp_path), tmp_path))
    second = _images(_project(_builder(tmp_path, library_version="tracer", injector_version="injector"), tmp_path))

    assert first["ssi-installer"].source_digest == second["ssi-installer"].source_digest
    assert first["weblog"].source_digest != second["weblog"].source_digest


@pytest.mark.parametrize(
    ("ci", "push", "expected"),
    [
        (False, False, (["ssi-installer", "weblog"], None)),
        (False, True, (["weblog"], ("base", "ssi-installer"))),
        (True, False, (["weblog"], ("base", "ssi-installer"))),
    ],
)
def test_publication_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    ci: bool,
    push: bool,
    expected: tuple[list[str], tuple[str, ...] | None],
) -> None:
    builder = _builder(tmp_path, push=push)
    builder.project = Mock()
    builder.project.build.return_value = {"weblog": "weblog-injection:latest"}
    docker_client = SimpleNamespace(images=SimpleNamespace(get=Mock()))
    monkeypatch.setattr(image_builder_module, "get_docker_client", lambda: docker_client)
    monkeypatch.setenv("PRIVATE_DOCKER_REGISTRY", "registry.example")
    monkeypatch.setenv("GITLAB_CI", "true") if ci else monkeypatch.delenv("GITLAB_CI", raising=False)

    builder._build_graph()  # noqa: SLF001

    built, pushed = expected
    builder.project.build.assert_called_once_with(built)
    if pushed is None:
        builder.project.push.assert_not_called()
    else:
        builder.project.push.assert_called_once_with(pushed)


@pytest.mark.parametrize(("ci", "push"), [(True, False), (False, True)])
def test_publication_requires_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, ci: bool, push: bool
) -> None:
    builder = _builder(tmp_path, push=push)
    monkeypatch.delenv("PRIVATE_DOCKER_REGISTRY", raising=False)
    monkeypatch.setenv("GITLAB_CI", "true") if ci else monkeypatch.delenv("GITLAB_CI", raising=False)
    with pytest.raises(DockerSSIImageError, match="requires PRIVATE_DOCKER_REGISTRY"):
        builder.configure()


def test_warm_cache_builds_only_the_per_run_images(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fixture(tmp_path)
    builder = _builder(tmp_path)
    builder.project = _project(builder, tmp_path)
    bake_definitions = []

    monkeypatch.setattr(
        ImageHandle,
        "cache_location",
        lambda image: CacheLocation.REMOTE if image.name == "ssi-installer" else CacheLocation.MISS,
    )
    monkeypatch.setattr(
        "rebuildr.project.DockerBakeBuilder",
        lambda: SimpleNamespace(build=lambda definition, **_kwargs: bake_definitions.append(definition)),
    )
    monkeypatch.setattr("rebuildr.project.pull_image", lambda *_args: None)
    monkeypatch.setattr("rebuildr.project.image_exists_locally", lambda *_args: True)
    monkeypatch.setattr(ImageHandle, "_verify_local", lambda *_args: None)
    monkeypatch.setattr(ImageHandle, "_materialize_local", lambda *_args: None)
    monkeypatch.setattr(
        image_builder_module,
        "get_docker_client",
        lambda: SimpleNamespace(images=SimpleNamespace(get=Mock())),
    )

    builder._build_graph()  # noqa: SLF001

    # One Buildx job, and the cached installer is referenced instead of rebuilt.
    assert len(bake_definitions) == 1
    targets = bake_definitions[0]["target"]
    assert set(targets) == {"rebuildr0_ssi", "rebuildr1_weblog"}
    assert targets["rebuildr0_ssi"]["contexts"]["installer-image"].startswith("docker-image://")
