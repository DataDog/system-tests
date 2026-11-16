from pathlib import Path

from utils import pytest, scenarios
from utils.docker_ssi.base_image_tag import BASE_IMAGE_BUILD_DIR, MAX_TAG_LENGTH, base_image_tag

NAME = "public_ecr_aws-lts-ubuntu-22_04_js2422_linux-amd64"
BUILD_ARGS: dict[str, str | None] = {
    "ARCH": "linux/amd64",
    "DD_LANG": "js",
    "RUNTIME_VERSIONS": "24.22.0",
    "BASE_IMAGE": "public.ecr.aws/lts/ubuntu:22.04",
}


@pytest.fixture
def build_dir(tmp_path: Path) -> Path:
    (tmp_path / "install_os_deps.sh").write_text("echo deps\n")
    (tmp_path / "base_lang.Dockerfile").write_text("FROM ubuntu\n")
    return tmp_path


@scenarios.test_the_test
def test_tag_is_the_name_and_a_hash(build_dir: Path) -> None:
    tag = base_image_tag(NAME, BUILD_ARGS, build_dir)
    name, content_hash = tag.rsplit("-", 1)
    assert name == NAME
    assert len(content_hash) == 12


@scenarios.test_the_test
def test_same_inputs_give_the_same_tag(build_dir: Path) -> None:
    assert base_image_tag(NAME, BUILD_ARGS, build_dir) == base_image_tag(NAME, dict(BUILD_ARGS), build_dir)


@scenarios.test_the_test
def test_changing_a_file_changes_the_tag(build_dir: Path) -> None:
    before = base_image_tag(NAME, BUILD_ARGS, build_dir)
    (build_dir / "install_os_deps.sh").write_text("echo deps libatomic\n")
    assert base_image_tag(NAME, BUILD_ARGS, build_dir) != before


@scenarios.test_the_test
def test_adding_a_file_changes_the_tag(build_dir: Path) -> None:
    before = base_image_tag(NAME, BUILD_ARGS, build_dir)
    (build_dir / "new_script.sh").write_text("echo new\n")
    assert base_image_tag(NAME, BUILD_ARGS, build_dir) != before


@scenarios.test_the_test
@pytest.mark.parametrize(
    ("arg", "value"),
    [
        ("RUNTIME_VERSIONS", "24.23.0"),
        ("RUNTIME_VERSIONS", None),
        ("ARCH", "linux/arm64"),
        ("DD_LANG", "python"),
        ("BASE_IMAGE", "public.ecr.aws/docker/library/debian:12"),
    ],
)
def test_changing_a_build_arg_changes_the_tag(build_dir: Path, arg: str, value: str | None) -> None:
    changed = {**BUILD_ARGS, arg: value}
    assert base_image_tag(NAME, changed, build_dir) != base_image_tag(NAME, BUILD_ARGS, build_dir)


@scenarios.test_the_test
def test_subfolders_and_hidden_files_are_ignored(build_dir: Path) -> None:
    before = base_image_tag(NAME, BUILD_ARGS, build_dir)
    (build_dir / "binaries").mkdir()
    (build_dir / "binaries" / "dd-library.deb").write_text("local binary\n")
    (build_dir / ".DS_Store").write_text("macos\n")
    assert base_image_tag(NAME, BUILD_ARGS, build_dir) == before


@scenarios.test_the_test
def test_long_names_are_cut_to_the_docker_limit(build_dir: Path) -> None:
    tag = base_image_tag("a" * 200, BUILD_ARGS, build_dir)
    assert len(tag) == MAX_TAG_LENGTH
    assert tag.startswith("a" * 100)


@scenarios.test_the_test
def test_real_build_dir_contains_the_base_dockerfiles() -> None:
    names = {path.name for path in BASE_IMAGE_BUILD_DIR.iterdir()}
    assert {"base_lang.Dockerfile", "base_deps.Dockerfile", "base_ssi_installer.Dockerfile"} <= names
