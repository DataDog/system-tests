from pathlib import Path
from types import SimpleNamespace
from typing import Never
from unittest.mock import Mock
from urllib.error import URLError

import pytest
from rebuildr import ImageHandle, Project
from rebuildr.project import CacheLocation

import utils.docker_ssi.image_builder as image_builder_module
from utils.docker_ssi.image_builder import DockerSSIImageBuilder, DockerSSIImageError


pytestmark = pytest.mark.scenario("TEST_THE_TEST")

_BASE_DIGEST = "sha256:" + "1" * 64
_OTHER_BASE_DIGEST = "sha256:" + "2" * 64


def _write_file(root: Path, relative_path: str, contents: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def _write_build_fixture(root: Path) -> None:
    files = {
        "utils/build/ssi/base/base_lang.Dockerfile": (
            "ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\n"
            "COPY base/install_os_deps.sh base/python_install_runtimes.sh /workdir/\n"
        ),
        "utils/build/ssi/base/base_deps.Dockerfile": (
            "ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\nCOPY base/install_os_deps.sh /workdir/\n"
        ),
        "utils/build/ssi/base/base_ssi_installer.Dockerfile": (
            "ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\n"
            "COPY base/install_script_ssi_installer.sh base/binaries/install_script_agent7.sh /workdir/\n"
        ),
        "utils/build/ssi/base/base_ssi.Dockerfile": (
            "ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\nCOPY base/install_script_ssi.sh base/binaries/* /workdir/\n"
        ),
        "utils/build/ssi/base/install_os_deps.sh": "#!/bin/sh\necho deps\n",
        "utils/build/ssi/base/healthcheck.sh": "#!/bin/sh\nexit 0\n",
        "utils/build/ssi/base/tested_components.sh": "#!/bin/sh\necho components\n",
        "utils/build/ssi/base/python_install_runtimes.sh": "#!/bin/sh\necho runtime\n",
        "utils/build/ssi/base/install_script_ssi_installer.sh": "#!/bin/sh\necho installer\n",
        "utils/build/ssi/base/install_script_ssi.sh": "#!/bin/sh\necho ssi\n",
        "utils/build/ssi/python/py-app.Dockerfile": "ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\nCOPY app.py /app/\n",
        "lib-injection/build/docker/python/app.py": "print('hello')\n",
    }
    for relative_path, contents in files.items():
        _write_file(root, relative_path, contents)


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
        "DOCKER_SSI",
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


def _snapshot_graphs(
    builder: DockerSSIImageBuilder,
    *,
    base_digest: str = _BASE_DIGEST,
    installer_contents: bytes = b"#!/bin/sh\necho downloaded installer\n",
):
    builder._resolved_base_image = f"ubuntu@{base_digest}"  # noqa: SLF001
    builder._installer_script_contents = installer_contents  # noqa: SLF001
    installer_input, temporary_path = builder._temporary_installer_script_input()  # noqa: SLF001
    try:
        cached_build = builder._create_cached_build(installer_input)  # noqa: SLF001
        cached_root = Project(cached_build, builder._root_dir).default  # noqa: SLF001
        builder._cached_build = cached_build  # noqa: SLF001
        builder._cached_root = cached_root  # noqa: SLF001
        movable_build = builder._create_movable_build(installer_input)  # noqa: SLF001
        movable_root = Project(movable_build, builder._root_dir).default  # noqa: SLF001
        builder._movable_build = movable_build  # noqa: SLF001
        builder._movable_root = movable_root  # noqa: SLF001
    finally:
        temporary_path.unlink()
    return cached_build, cached_root, movable_build, movable_root


def test_cached_and_movable_graphs_use_image_references_and_propagate_source_digest(tmp_path: Path) -> None:
    _write_build_fixture(tmp_path)
    cached_build, cached_root, movable_build, movable_root = _snapshot_graphs(_builder(tmp_path))

    cached_definition = cached_build.images["ssi-installer"]
    assert cached_definition.image_refs == {"cached-base": cached_build.images["base"]}
    assert cached_definition.content_tag is True
    assert cached_definition.tag == "latest"
    assert cached_root.metadata["manifest"]["image_references"] == [
        {
            "alias": "cached-base",
            "source_digest": cached_root.image_refs["cached-base"].source_digest,
        }
    ]

    movable_definition = movable_build.images["weblog"]
    assert movable_definition.image_refs == {"ssi-image": movable_build.images["ssi"]}
    assert movable_build.images["ssi"].content_tag is False
    assert movable_definition.content_tag is False
    assert movable_definition.repository == "weblog-injection"
    assert movable_definition.tag == "latest"
    assert movable_root.metadata["manifest"]["image_references"] == [
        {
            "alias": "ssi-image",
            "source_digest": movable_root.image_refs["ssi-image"].source_digest,
        }
    ]


def test_reusable_identity_tracks_base_platform_runtime_and_source_files(tmp_path: Path) -> None:
    _write_build_fixture(tmp_path)
    baseline_builder = _builder(tmp_path)
    _, baseline, _, _ = _snapshot_graphs(baseline_builder)

    _, changed_digest, _, _ = _snapshot_graphs(_builder(tmp_path), base_digest=_OTHER_BASE_DIGEST)
    _, changed_platform, _, _ = _snapshot_graphs(_builder(tmp_path, arch="linux/arm64"))
    _, changed_runtime, _, _ = _snapshot_graphs(_builder(tmp_path, runtime="3.11.10"))
    _, changed_installer, _, _ = _snapshot_graphs(_builder(tmp_path), installer_contents=b"changed installer")

    _write_file(
        tmp_path,
        "utils/build/ssi/base/base_lang.Dockerfile",
        "ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\nRUN echo changed\n",
    )
    _, changed_dockerfile, _, _ = _snapshot_graphs(_builder(tmp_path))
    _write_build_fixture(tmp_path)
    _write_file(tmp_path, "utils/build/ssi/base/python_install_runtimes.sh", "#!/bin/sh\necho changed\n")
    _, changed_runtime_script, _, _ = _snapshot_graphs(_builder(tmp_path))

    changed = {
        changed_digest.source_digest,
        changed_platform.source_digest,
        changed_runtime.source_digest,
        changed_dockerfile.source_digest,
        changed_runtime_script.source_digest,
        changed_installer.source_digest,
    }
    assert baseline.source_digest not in changed
    assert len(changed) == 6


def test_tracer_and_injector_versions_change_only_the_movable_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_build_fixture(tmp_path)
    monkeypatch.setattr(image_builder_module.uuid, "uuid4", lambda: SimpleNamespace(hex="fixed-nonce"))

    _, first_cached, _, first_movable = _snapshot_graphs(_builder(tmp_path))
    _, second_cached, _, second_movable = _snapshot_graphs(
        _builder(tmp_path, library_version="pipeline-123", injector_version="pipeline-456")
    )

    assert first_cached.source_digest == second_cached.source_digest
    assert first_movable.source_digest != second_movable.source_digest


@pytest.mark.parametrize(
    ("gitlab_ci", "push", "expected_action"), [(False, False, "build"), (False, True, "push"), (True, False, "push")]
)
def test_publication_policy_selects_build_or_push(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    gitlab_ci: bool,
    push: bool,
    expected_action: str,
) -> None:
    builder = _builder(tmp_path, push=push)
    cached = Mock()
    cached.build.return_value = "cached"
    cached.push.return_value = "cached"
    movable = Mock()
    movable.build.return_value = "weblog-injection:latest"
    builder._cached_root = cached  # noqa: SLF001
    builder._movable_root = movable  # noqa: SLF001
    docker_image = object()
    docker_client = SimpleNamespace(images=SimpleNamespace(get=Mock(return_value=docker_image)))
    monkeypatch.setattr(image_builder_module, "get_docker_client", lambda: docker_client)
    monkeypatch.setenv("PRIVATE_DOCKER_REGISTRY", "registry.example")
    if gitlab_ci:
        monkeypatch.setenv("GITLAB_CI", "true")
    else:
        monkeypatch.delenv("GITLAB_CI", raising=False)

    builder.build_weblog()

    assert cached.build.call_count == (expected_action == "build")
    assert cached.push.call_count == (expected_action == "push")
    movable.build.assert_called_once_with()
    docker_client.images.get.assert_called_once_with("weblog-injection:latest")
    assert builder._weblog_docker_image is docker_image  # noqa: SLF001


@pytest.mark.parametrize(("gitlab_ci", "push"), [(True, False), (False, True)])
def test_publication_requires_registry_early(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    gitlab_ci: bool,
    push: bool,
) -> None:
    builder = _builder(tmp_path, push=push)
    monkeypatch.delenv("PRIVATE_DOCKER_REGISTRY", raising=False)
    if gitlab_ci:
        monkeypatch.setenv("GITLAB_CI", "true")
    else:
        monkeypatch.delenv("GITLAB_CI", raising=False)

    with pytest.raises(DockerSSIImageError, match="requires PRIVATE_DOCKER_REGISTRY"):
        builder.configure()


def test_local_registry_configuration_does_not_enable_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    builder = _builder(tmp_path)
    monkeypatch.setenv("PRIVATE_DOCKER_REGISTRY", "registry.example")
    monkeypatch.delenv("GITLAB_CI", raising=False)

    builder._validate_publication_policy()  # noqa: SLF001


def test_warm_remote_cache_skips_cached_dag_but_runs_movable_dag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_build_fixture(tmp_path)
    builder = _builder(tmp_path)
    _, _, _, _ = _snapshot_graphs(builder)
    bake_calls: list[tuple[dict[str, object], dict[str, object]]] = []

    def cache_location(image: ImageHandle) -> CacheLocation:
        return CacheLocation.REMOTE if image.name == "ssi-installer" else CacheLocation.MISS

    class Builder:
        def build(self, definition: dict[str, object], **kwargs: object) -> None:
            bake_calls.append((definition, kwargs))

    monkeypatch.setattr(image_builder_module.ImageHandle, "cache_location", cache_location)
    monkeypatch.setattr("rebuildr.project.DockerBakeBuilder", Builder)
    monkeypatch.setattr("rebuildr.project.pull_image", lambda *_args: None)
    monkeypatch.setattr("rebuildr.project.image_exists_locally", lambda *_args: True)
    monkeypatch.setattr(image_builder_module.ImageHandle, "_verify_local", lambda *_args: None)
    monkeypatch.setattr(image_builder_module.ImageHandle, "_materialize_local", lambda *_args: None)
    docker_client = SimpleNamespace(images=SimpleNamespace(get=Mock(return_value=object())))
    monkeypatch.setattr(image_builder_module, "get_docker_client", lambda: docker_client)
    monkeypatch.delenv("GITLAB_CI", raising=False)
    monkeypatch.delenv("PRIVATE_DOCKER_REGISTRY", raising=False)

    builder.build_weblog()

    assert len(bake_calls) == 1
    definition = bake_calls[0][0]
    targets = definition["target"]
    group = definition["group"]
    assert isinstance(targets, dict)
    assert isinstance(group, dict)
    default_group = group["default"]
    assert isinstance(default_group, dict)
    assert set(targets) == {"rebuildr0_ssi", "rebuildr1_weblog"}
    assert default_group["targets"] == ["rebuildr1_weblog"]


def test_base_digest_resolution_returns_an_immutable_reference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    builder = _builder(tmp_path)
    output = f"Name: ubuntu:24.04\nMediaType: application/vnd.oci.image.index.v1+json\nDigest: {_BASE_DIGEST}\n"

    def inspect_image(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(stdout=output)

    monkeypatch.setattr(image_builder_module.subprocess, "run", inspect_image)

    assert builder._resolve_base_image_digest() == f"ubuntu@{_BASE_DIGEST}"  # noqa: SLF001


def test_installer_download_failure_is_actionable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_build_fixture(tmp_path)
    builder = _builder(tmp_path)

    def fail_download(*_args: object, **_kwargs: object) -> Never:
        raise URLError("offline")

    monkeypatch.setattr(image_builder_module, "urlopen", fail_download)

    with pytest.raises(DockerSSIImageError, match="Check network access"):
        builder._load_installer_script()  # noqa: SLF001
