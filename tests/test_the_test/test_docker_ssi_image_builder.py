import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from rebuildr import ImageHandle
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


def _graphs(
    builder: DockerSSIImageBuilder,
    root: Path,
    *,
    digest: str = _BASE_DIGEST,
    installer: bytes = b"installer",
) -> tuple[ImageHandle, ImageHandle]:
    (root / "installer.sh").write_bytes(installer)
    return builder._load_projects(f"ubuntu@{digest}", "installer.sh")  # noqa: SLF001


def test_rebuildr_graphs_and_cached_identity(tmp_path: Path) -> None:
    _fixture(tmp_path)
    cached, movable = _graphs(_builder(tmp_path), tmp_path)

    assert set(cached.image_refs) == {"cached-base"}
    assert cached.definition.tag == "latest"
    assert (
        cached.metadata["manifest"]["image_references"][0]["source_digest"]
        == cached.image_refs["cached-base"].source_digest
    )
    assert set(movable.image_refs) == {"ssi-image"}
    assert movable.definition.repository == "weblog-injection"
    assert movable.definition.content_tag is False
    assert movable.image_refs["ssi-image"].definition.content_tag is False

    changed = [
        _graphs(_builder(tmp_path), tmp_path, digest="sha256:" + "2" * 64)[0],
        _graphs(_builder(tmp_path, arch="linux/arm64"), tmp_path)[0],
        _graphs(_builder(tmp_path, runtime="3.11.10"), tmp_path)[0],
        _graphs(_builder(tmp_path), tmp_path, installer=b"changed")[0],
    ]
    (tmp_path / "utils/build/ssi/base/base_lang.Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    changed.append(_graphs(_builder(tmp_path), tmp_path)[0])
    assert all(image.source_digest != cached.source_digest for image in changed)


def test_versions_change_only_the_movable_graph(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fixture(tmp_path)
    monkeypatch.setattr(image_builder_module.uuid, "uuid4", lambda: SimpleNamespace(hex="nonce"))
    first_cached, first_movable = _graphs(_builder(tmp_path), tmp_path)
    second_cached, second_movable = _graphs(
        _builder(tmp_path, library_version="tracer", injector_version="injector"), tmp_path
    )

    assert first_cached.source_digest == second_cached.source_digest
    assert first_movable.source_digest != second_movable.source_digest


@pytest.mark.parametrize(
    ("ci", "push", "expected"), [(False, False, "build"), (False, True, "push"), (True, False, "push")]
)
def test_publication_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, ci: bool, push: bool, expected: str
) -> None:
    builder = _builder(tmp_path, push=push)
    builder.cached_root = Mock()
    builder.movable_root = Mock()
    builder.movable_root.build.return_value = "weblog-injection:latest"
    docker_client = SimpleNamespace(images=SimpleNamespace(get=Mock()))
    monkeypatch.setattr(image_builder_module, "get_docker_client", lambda: docker_client)
    monkeypatch.setenv("PRIVATE_DOCKER_REGISTRY", "registry.example")
    monkeypatch.setenv("GITLAB_CI", "true") if ci else monkeypatch.delenv("GITLAB_CI", raising=False)

    builder.build_weblog()

    getattr(builder.cached_root, expected).assert_called_once_with()
    builder.movable_root.build.assert_called_once_with()


@pytest.mark.parametrize(("ci", "push"), [(True, False), (False, True)])
def test_publication_requires_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, ci: bool, push: bool
) -> None:
    builder = _builder(tmp_path, push=push)
    monkeypatch.delenv("PRIVATE_DOCKER_REGISTRY", raising=False)
    monkeypatch.setenv("GITLAB_CI", "true") if ci else monkeypatch.delenv("GITLAB_CI", raising=False)
    with pytest.raises(DockerSSIImageError, match="requires PRIVATE_DOCKER_REGISTRY"):
        builder.configure()


def test_warm_cache_skips_cached_graph_but_runs_movable_graph(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fixture(tmp_path)
    builder = _builder(tmp_path)
    builder.cached_root, builder.movable_root = _graphs(builder, tmp_path)
    bake_definitions = []

    monkeypatch.setattr(
        image_builder_module.ImageHandle,
        "cache_location",
        lambda image: CacheLocation.REMOTE if image.name == "ssi-installer" else CacheLocation.MISS,
    )
    monkeypatch.setattr(
        "rebuildr.project.DockerBakeBuilder",
        lambda: SimpleNamespace(build=lambda definition, **_kwargs: bake_definitions.append(definition)),
    )
    monkeypatch.setattr("rebuildr.project.pull_image", lambda *_args: None)
    monkeypatch.setattr("rebuildr.project.image_exists_locally", lambda *_args: True)
    monkeypatch.setattr(image_builder_module.ImageHandle, "_verify_local", lambda *_args: None)
    monkeypatch.setattr(image_builder_module.ImageHandle, "_materialize_local", lambda *_args: None)
    monkeypatch.setattr(
        image_builder_module,
        "get_docker_client",
        lambda: SimpleNamespace(images=SimpleNamespace(get=Mock())),
    )

    builder.build_weblog()

    assert len(bake_definitions) == 1
    assert set(bake_definitions[0]["target"]) == {"rebuildr0_ssi", "rebuildr1_weblog"}
