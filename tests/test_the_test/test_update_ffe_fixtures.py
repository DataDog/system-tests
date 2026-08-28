# ruff: noqa: SLF001

from pathlib import Path

import pytest

from utils import scenarios
from utils.scripts import update_ffe_fixtures


@scenarios.test_the_test
@pytest.mark.parametrize("fixture_ref", ["main", "feature/fixture-update", "v1.2.3", "ea8b5cc5"])
def test_validate_fixture_ref_accepts_git_refs(fixture_ref: str) -> None:
    update_ffe_fixtures._validate_fixture_ref(fixture_ref)


@scenarios.test_the_test
@pytest.mark.parametrize("fixture_ref", ["", "-main", "../main", "main^", "main ref"])
def test_validate_fixture_ref_rejects_unsafe_refs(fixture_ref: str) -> None:
    with pytest.raises(ValueError, match="Invalid FFE fixture ref"):
        update_ffe_fixtures._validate_fixture_ref(fixture_ref)


@scenarios.test_the_test
def test_copy_fixture_snapshot_uses_client_disallow_list(tmp_path: Path) -> None:
    source = tmp_path / "source"
    snapshot = tmp_path / "snapshot"
    (source / "evaluation-cases").mkdir(parents=True)
    snapshot.mkdir()
    (source / "evaluation-cases" / "case.json").write_text("[]", encoding="utf-8")
    (source / "ufc-config.json").write_text("{}", encoding="utf-8")
    (source / "README.md").write_text("upstream documentation", encoding="utf-8")

    update_ffe_fixtures._copy_fixture_snapshot(source, snapshot)

    assert (snapshot / "ufc-config.json").is_file()
    assert (snapshot / "evaluation-cases" / "case.json").is_file()
    assert not (snapshot / "README.md").exists()


@scenarios.test_the_test
def test_copy_fixture_snapshot_rejects_symbolic_links(tmp_path: Path) -> None:
    source = tmp_path / "source"
    snapshot = tmp_path / "snapshot"
    source.mkdir()
    snapshot.mkdir()
    target = source / "target.json"
    target.write_text("{}", encoding="utf-8")
    (source / "linked.json").symlink_to(target)

    with pytest.raises(ValueError, match="Refusing to copy symbolic link"):
        update_ffe_fixtures._copy_fixture_snapshot(source, snapshot)


@scenarios.test_the_test
def test_validate_fixture_snapshot_counts_evaluations(tmp_path: Path) -> None:
    cases_directory = tmp_path / "evaluation-cases"
    cases_directory.mkdir()
    (tmp_path / "ufc-config.json").write_text("{}", encoding="utf-8")
    (cases_directory / "first.json").write_text('[{"flag": "one"}]', encoding="utf-8")
    (cases_directory / "second.json").write_text('[{"flag": "two"}, {"flag": "three"}]', encoding="utf-8")

    assert update_ffe_fixtures._validate_fixture_snapshot(tmp_path) == 3


@scenarios.test_the_test
def test_have_same_contents_ignores_generated_source_metadata(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    destination = tmp_path / "destination"
    snapshot.mkdir()
    destination.mkdir()
    (snapshot / "fixture.json").write_text("{}", encoding="utf-8")
    (destination / "fixture.json").write_text("{}", encoding="utf-8")
    (destination / "SOURCE.md").write_text("generated", encoding="utf-8")

    assert update_ffe_fixtures._have_same_contents(snapshot, destination)

    (destination / "fixture.json").write_text('{"changed": true}', encoding="utf-8")
    assert not update_ffe_fixtures._have_same_contents(snapshot, destination)
