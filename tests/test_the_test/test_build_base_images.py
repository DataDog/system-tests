from pathlib import Path
import subprocess
import tempfile
import textwrap

import pytest

from utils import scenarios
from utils.scripts import build_base_images
from utils.scripts.build_base_images import (
    _dependency_paths,
    _files_under,
    compute_hash,
    materialize_build_context,
    parse_copy_dependencies,
)


def _write_dockerfile(tmp_path: Path, content: str) -> Path:
    dockerfile = tmp_path / "some.base.Dockerfile"
    dockerfile.write_text(textwrap.dedent(content))
    return dockerfile


@scenarios.test_the_test
class Test_ParseCopyDependencies:
    """Unit tests for utils.scripts.build_base_images.parse_copy_dependencies, which derives
    a base image's dependencies from the `COPY` instructions of its Dockerfile.
    """

    def test_single_copy(self, tmp_path: Path):
        dockerfile = _write_dockerfile(
            tmp_path,
            """\
            FROM node:18-alpine
            COPY app.js .
            """,
        )
        assert parse_copy_dependencies(dockerfile) == ["app.js"]

    def test_multiple_copy_instructions(self, tmp_path: Path):
        dockerfile = _write_dockerfile(
            tmp_path,
            """\
            FROM node:18-alpine
            COPY express /usr/app
            COPY express4/package.json ./
            COPY express4/bun.lock ./
            COPY nft-prune.mjs ./
            """,
        )
        assert parse_copy_dependencies(dockerfile) == [
            "express",
            "express4/package.json",
            "express4/bun.lock",
            "nft-prune.mjs",
        ]

    def test_copy_with_flags_is_parsed(self, tmp_path: Path):
        dockerfile = _write_dockerfile(
            tmp_path,
            """\
            FROM node:18-alpine
            COPY --chown=node:node app.js .
            """,
        )
        assert parse_copy_dependencies(dockerfile) == ["app.js"]

    def test_copy_from_external_image_is_skipped(self, tmp_path: Path):
        dockerfile = _write_dockerfile(
            tmp_path,
            """\
            FROM node:18-alpine
            COPY --from=oven/bun:1.3.13-alpine /usr/local/bin/bun /usr/local/bin/bun
            COPY app.js .
            """,
        )
        assert parse_copy_dependencies(dockerfile) == ["app.js"]

    def test_copy_from_build_stage_is_skipped(self, tmp_path: Path):
        dockerfile = _write_dockerfile(
            tmp_path,
            """\
            FROM golang:1.22 AS build
            RUN echo build

            FROM alpine
            COPY --from=build /app/weblog /app/weblog
            COPY app.sh .
            """,
        )
        assert parse_copy_dependencies(dockerfile) == ["app.sh"]

    def test_line_continuation_is_joined(self, tmp_path: Path):
        dockerfile = _write_dockerfile(
            tmp_path,
            """\
            FROM node:18-alpine
            COPY \\
                app.js \\
                .
            """,
        )
        assert parse_copy_dependencies(dockerfile) == ["app.js"]

    def test_lowercase_instruction_is_parsed(self, tmp_path: Path):
        dockerfile = _write_dockerfile(
            tmp_path,
            """\
            FROM node:18-alpine
            copy app.js .
            """,
        )
        assert parse_copy_dependencies(dockerfile) == ["app.js"]

    def test_comments_and_blank_lines_are_ignored(self, tmp_path: Path):
        dockerfile = _write_dockerfile(
            tmp_path,
            """\
            FROM node:18-alpine

            # This is a comment
            COPY app.js .

            # docker build ...
            """,
        )
        assert parse_copy_dependencies(dockerfile) == ["app.js"]

    def test_run_without_mount_is_allowed(self, tmp_path: Path):
        dockerfile = _write_dockerfile(
            tmp_path,
            """\
            FROM node:18-alpine
            COPY app.js .
            RUN node --version
            """,
        )
        assert parse_copy_dependencies(dockerfile) == ["app.js"]

    def test_no_copy_instructions_returns_empty_list(self, tmp_path: Path):
        dockerfile = _write_dockerfile(
            tmp_path,
            """\
            FROM node:18-alpine
            RUN node --version
            """,
        )
        assert parse_copy_dependencies(dockerfile) == []

    def test_add_is_rejected(self, tmp_path: Path):
        dockerfile = _write_dockerfile(
            tmp_path,
            """\
            FROM node:18-alpine
            ADD app.js .
            """,
        )
        with pytest.raises(ValueError, match="ADD is not allowed"):
            parse_copy_dependencies(dockerfile)

    def test_add_with_glob_is_rejected(self, tmp_path: Path):
        dockerfile = _write_dockerfile(
            tmp_path,
            """\
            FROM node:18-alpine
            ADD binaries* /binaries/
            """,
        )
        with pytest.raises(ValueError, match="ADD is not allowed"):
            parse_copy_dependencies(dockerfile)

    def test_run_mount_bind_is_rejected(self, tmp_path: Path):
        dockerfile = _write_dockerfile(
            tmp_path,
            """\
            FROM golang:1.22
            RUN --mount=type=bind,source=.,target=/src \\
                go build ./...
            """,
        )
        with pytest.raises(ValueError, match="RUN --mount is not allowed"):
            parse_copy_dependencies(dockerfile)

    def test_run_mount_cache_is_rejected(self, tmp_path: Path):
        dockerfile = _write_dockerfile(
            tmp_path,
            """\
            FROM python:3.11
            RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt
            """,
        )
        with pytest.raises(ValueError, match="RUN --mount is not allowed"):
            parse_copy_dependencies(dockerfile)

    def test_multi_source_copy_is_rejected(self, tmp_path: Path):
        dockerfile = _write_dockerfile(
            tmp_path,
            """\
            FROM node:18-alpine
            COPY app.js dsm.js rasp.js ./
            """,
        )
        with pytest.raises(ValueError, match="exactly one source"):
            parse_copy_dependencies(dockerfile)

    def test_copy_with_no_destination_is_rejected(self, tmp_path: Path):
        dockerfile = _write_dockerfile(
            tmp_path,
            """\
            FROM node:18-alpine
            COPY app.js
            """,
        )
        with pytest.raises(ValueError, match="exactly one source"):
            parse_copy_dependencies(dockerfile)


@scenarios.test_the_test
class Test_DependencyPaths:
    """Unit tests for utils.scripts.build_base_images._dependency_paths, which resolves each
    COPY source parsed by parse_copy_dependencies() against `context_root` (the Dockerfile's own
    directory), expanding glob wildcards along the way (see the module docstring, "Wildcard
    sources"), then flattens each match to its constituent non-gitignored files via
    `_files_under` (see Test_FilesUnder). Every returned path is relative to `context_root`,
    which is also the only boundary a COPY source is allowed to stay within (see the "escapes"
    test below) — REPO_ROOT plays no part in this resolution, so these tests don't need to touch
    it at all.
    """

    @pytest.fixture(autouse=True)
    def _git_repo(self, tmp_path: Path):
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)

    def test_literal_source_resolves_to_itself(self, tmp_path: Path):
        (tmp_path / "app.js").write_text("")
        dockerfile = _write_dockerfile(
            tmp_path,
            """\
            FROM node:18-alpine
            COPY app.js .
            """,
        )
        assert _dependency_paths(tmp_path, dockerfile) == [Path("app.js")]

    def test_literal_directory_source_flattens_to_its_files(self, tmp_path: Path):
        (tmp_path / "express").mkdir()
        (tmp_path / "express" / "app.js").write_text("")
        (tmp_path / "express" / "auth.js").write_text("")
        dockerfile = _write_dockerfile(
            tmp_path,
            """\
            FROM node:18-alpine
            COPY express /usr/app
            """,
        )
        assert _dependency_paths(tmp_path, dockerfile) == [
            Path("express/app.js"),
            Path("express/auth.js"),
        ]

    def test_wildcard_source_expands_to_every_match(self, tmp_path: Path):
        (tmp_path / "package.json").write_text("")
        (tmp_path / "package-lock.json").write_text("")
        (tmp_path / "app.js").write_text("")
        dockerfile = _write_dockerfile(
            tmp_path,
            """\
            FROM node:18-alpine
            COPY *.json .
            """,
        )
        assert _dependency_paths(tmp_path, dockerfile) == [
            Path("package-lock.json"),
            Path("package.json"),
        ]

    def test_overlapping_sources_are_deduplicated(self, tmp_path: Path):
        # A directory dependency and one of its own files listed separately (as in
        # `COPY express4-typescript /usr/app` + `COPY express4-typescript/package.json ./` in a
        # real base Dockerfile) overlap: the file must only appear once in the final list.
        (tmp_path / "express").mkdir()
        (tmp_path / "express" / "app.js").write_text("")
        (tmp_path / "express" / "package.json").write_text("")
        dockerfile = _write_dockerfile(
            tmp_path,
            """\
            FROM node:18-alpine
            COPY express /usr/app
            COPY express/package.json ./
            """,
        )
        assert _dependency_paths(tmp_path, dockerfile) == [
            Path("express/app.js"),
            Path("express/package.json"),
        ]

    def test_wildcard_source_matching_nothing_is_rejected(self, tmp_path: Path):
        dockerfile = _write_dockerfile(
            tmp_path,
            """\
            FROM node:18-alpine
            COPY *.json .
            """,
        )
        with pytest.raises(ValueError, match="matched no files"):
            _dependency_paths(tmp_path, dockerfile)

    def test_literal_source_matching_nothing_is_rejected(self, tmp_path: Path):
        dockerfile = _write_dockerfile(
            tmp_path,
            """\
            FROM node:18-alpine
            COPY does-not-exist.txt .
            """,
        )
        with pytest.raises(ValueError, match="matched no files"):
            _dependency_paths(tmp_path, dockerfile)

    def test_source_escaping_context_root_is_rejected(self, tmp_path: Path):
        # A COPY source that reaches into a sibling library's directory (e.g. a nodejs base
        # Dockerfile depending on something under utils/build/docker/python/) must be rejected,
        # regardless of whether the resolved path stays inside the repository or not.
        context_root = tmp_path / "nodejs"
        sibling_dir = tmp_path / "python"
        context_root.mkdir()
        sibling_dir.mkdir()
        (sibling_dir / "weblog_metadata.yml").write_text("")

        dockerfile = _write_dockerfile(
            context_root,
            """\
            FROM node:18-alpine
            COPY ../python/weblog_metadata.yml .
            """,
        )
        with pytest.raises(ValueError, match="escapes the Dockerfile's context directory"):
            _dependency_paths(context_root, dockerfile)


@scenarios.test_the_test
class Test_FilesUnder:
    """Unit tests for utils.scripts.build_base_images._files_under, which lists the files under
    a dependency path that should actually be hashed/hardlinked: every git-tracked file, plus
    every untracked-but-not-gitignored file, but never anything gitignored (e.g. a locally
    installed, never-committed node_modules/ sitting under a dependency directory). Filtering is
    based purely on .gitignore rules, not on whether a file is committed or staged.
    """

    @pytest.fixture(autouse=True)
    def _git_repo(self, tmp_path: Path):
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)

    def test_tracked_file_is_included(self, tmp_path: Path):
        (tmp_path / "app.js").write_text("")
        subprocess.run(["git", "add", "app.js"], cwd=tmp_path, check=True)

        assert _files_under(tmp_path, Path("app.js")) == [Path("app.js")]

    def test_untracked_but_not_gitignored_file_is_included(self, tmp_path: Path):
        # Never `git add`-ed, and not covered by any .gitignore rule: this script must not
        # require content to be committed, or even staged, to be picked up.
        (tmp_path / "app.js").write_text("")

        assert _files_under(tmp_path, Path("app.js")) == [Path("app.js")]

    def test_gitignored_file_under_a_directory_dependency_is_excluded(self, tmp_path: Path):
        (tmp_path / ".gitignore").write_text("node_modules/\n")
        (tmp_path / "express").mkdir()
        (tmp_path / "express" / "app.js").write_text("")
        (tmp_path / "express" / "node_modules").mkdir()
        (tmp_path / "express" / "node_modules" / "some_dep.js").write_text("")
        subprocess.run(["git", "add", "express/app.js", ".gitignore"], cwd=tmp_path, check=True)

        assert _files_under(tmp_path, Path("express")) == [Path("express/app.js")]

    def test_dependency_entirely_gitignored_raises_with_an_explicit_message(self, tmp_path: Path):
        (tmp_path / ".gitignore").write_text("secret.txt\n")
        (tmp_path / "secret.txt").write_text("")

        with pytest.raises(ValueError, match="every file under it is gitignored"):
            _files_under(tmp_path, Path("secret.txt"))

    def test_directory_dependency_entirely_gitignored_raises_with_an_explicit_message(self, tmp_path: Path):
        (tmp_path / ".gitignore").write_text("ignored_dir/\n")
        (tmp_path / "ignored_dir").mkdir()
        (tmp_path / "ignored_dir" / "x.txt").write_text("")

        with pytest.raises(ValueError, match="every file under it is gitignored"):
            _files_under(tmp_path, Path("ignored_dir"))

    def test_outside_a_git_repository_raises(self):
        # This test needs a directory that is guaranteed not to be inside any git repository
        # (unlike tmp_path, which _git_repo's autouse fixture always `git init`s), so it uses a
        # fully independent temporary directory instead.
        with tempfile.TemporaryDirectory() as outside_any_repo_str:
            outside_any_repo = Path(outside_any_repo_str)
            (outside_any_repo / "app.js").write_text("")

            with pytest.raises(subprocess.CalledProcessError):
                _files_under(outside_any_repo, Path("app.js"))


@scenarios.test_the_test
class Test_MaterializeBuildContext:
    """Unit tests for utils.scripts.build_base_images.materialize_build_context, which
    hardlinks every dependency (plus the Dockerfile itself) into an isolated build directory.
    """

    @pytest.fixture(autouse=True)
    def _git_repo(self, tmp_path: Path):
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)

    def test_overlapping_dependencies_are_deduplicated(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        # Regression test: a directory dependency and one of its own files listed separately as
        # a second dependency (as in `COPY express4-typescript /usr/app` +
        # `COPY express4-typescript/package.json ./` in a real base Dockerfile) overlap, so the
        # same source file would otherwise be hardlinked into the same destination twice.
        monkeypatch.setattr(build_base_images, "BUILD_CONTEXT_ROOT", tmp_path / "build")

        (tmp_path / "express4-typescript").mkdir()
        (tmp_path / "express4-typescript" / "package.json").write_text("{}")
        (tmp_path / "express4-typescript" / "app.ts").write_text("")
        dockerfile = _write_dockerfile(
            tmp_path,
            """\
            FROM node:18-alpine
            COPY express4-typescript /usr/app
            COPY express4-typescript/package.json ./
            """,
        )
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)

        dependencies = _dependency_paths(tmp_path, dockerfile)
        build_dir = materialize_build_context("somelib", "sometarget", tmp_path, dockerfile, dependencies)

        materialized = sorted(p.relative_to(build_dir) for p in build_dir.rglob("*") if p.is_file())
        assert materialized == [
            Path("express4-typescript/app.ts"),
            Path("express4-typescript/package.json"),
            Path(dockerfile.name),
        ]


@scenarios.test_the_test
class Test_ComputeHash:
    """Unit tests for utils.scripts.build_base_images.compute_hash, which hashes the resolved
    bake config (minus tags) together with the path and content of every file in an already
    materialized build directory (see materialize_build_context) — not a separate read of the
    dependency paths, so there is nothing git- or context_root-related to set up here.
    """

    def test_same_directory_and_config_produce_the_same_hash(self, tmp_path: Path):
        (tmp_path / "app.js").write_text("console.log(1);")
        bake_config = {"context": ".", "dockerfile": "x.base.Dockerfile", "tags": ["x"]}

        assert compute_hash(tmp_path, bake_config) == compute_hash(tmp_path, bake_config)

    def test_different_file_content_changes_the_hash(self, tmp_path_factory: pytest.TempPathFactory):
        dir_a = tmp_path_factory.mktemp("a")
        dir_b = tmp_path_factory.mktemp("b")
        (dir_a / "app.js").write_text("console.log(1);")
        (dir_b / "app.js").write_text("console.log(2);")
        bake_config = {"tags": ["x"]}

        assert compute_hash(dir_a, bake_config) != compute_hash(dir_b, bake_config)

    def test_different_file_name_changes_the_hash(self, tmp_path_factory: pytest.TempPathFactory):
        dir_a = tmp_path_factory.mktemp("a")
        dir_b = tmp_path_factory.mktemp("b")
        (dir_a / "app.js").write_text("same content")
        (dir_b / "index.js").write_text("same content")
        bake_config = {"tags": ["x"]}

        assert compute_hash(dir_a, bake_config) != compute_hash(dir_b, bake_config)

    def test_different_bake_config_changes_the_hash(self, tmp_path: Path):
        (tmp_path / "app.js").write_text("console.log(1);")

        assert compute_hash(tmp_path, {"args": {"PHP_VERSION": "8.0"}, "tags": ["x"]}) != compute_hash(
            tmp_path, {"args": {"PHP_VERSION": "8.1"}, "tags": ["x"]}
        )

    def test_tags_are_excluded_from_the_hash(self, tmp_path: Path):
        (tmp_path / "app.js").write_text("console.log(1);")

        assert compute_hash(tmp_path, {"tags": ["x"]}) == compute_hash(tmp_path, {"tags": ["y"]})
