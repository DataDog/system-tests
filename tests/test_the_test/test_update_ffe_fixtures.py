# ruff: noqa: SLF001

from pathlib import Path
import shutil

from utils import pytest

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


def _write_feature_suite(source: Path, cases: str = '[{"flag": "dependent"}]') -> None:
    suite = source / "evaluation-suites" / "dependent-flags"
    (suite / "cases").mkdir(parents=True)
    (suite / "ufc-config.json").write_text('{"flags": {"dependent": {}}}', encoding="utf-8")
    (suite / "cases" / "dependent.json").write_text(cases, encoding="utf-8")


@scenarios.test_the_test
def test_copy_fixture_snapshot_imports_only_rules_based_evaluator_data(tmp_path: Path) -> None:
    source = tmp_path / "source"
    snapshot = tmp_path / "snapshot"
    (source / "evaluation-cases").mkdir(parents=True)
    snapshot.mkdir()
    (source / "evaluation-cases" / "case.json").write_text("[]", encoding="utf-8")
    (source / "ufc-config.json").write_text("{}", encoding="utf-8")
    _write_feature_suite(source)
    (source / "README.md").write_text("upstream documentation", encoding="utf-8")
    (source / "AGENTS.md").write_text("upstream instructions", encoding="utf-8")
    (source / "precomputed-assignments").mkdir()

    update_ffe_fixtures._copy_fixture_snapshot(source, snapshot)

    assert (snapshot / "ufc-config.json").is_file()
    assert (snapshot / "evaluation-cases" / "case.json").is_file()
    assert (snapshot / "evaluation-suites" / "dependent-flags" / "ufc-config.json").is_file()
    assert (snapshot / "evaluation-suites" / "dependent-flags" / "cases" / "dependent.json").is_file()
    assert not (snapshot / "README.md").exists()
    assert not (snapshot / "AGENTS.md").exists()
    assert not (snapshot / "precomputed-assignments").exists()


@scenarios.test_the_test
def test_copy_fixture_snapshot_rejects_symbolic_links(tmp_path: Path) -> None:
    source = tmp_path / "source"
    snapshot = tmp_path / "snapshot"
    source.mkdir()
    snapshot.mkdir()
    (source / "evaluation-cases").mkdir()
    (source / "ufc-config.json").write_text("{}", encoding="utf-8")
    _write_feature_suite(source)
    target = source / "target.json"
    target.write_text("{}", encoding="utf-8")
    (source / "evaluation-cases" / "linked.json").symlink_to(target)

    with pytest.raises(ValueError, match="Refusing to copy symbolic link"):
        update_ffe_fixtures._copy_fixture_snapshot(source, snapshot)


@scenarios.test_the_test
def test_validate_fixture_snapshot_counts_evaluations(tmp_path: Path) -> None:
    cases_directory = tmp_path / "evaluation-cases"
    cases_directory.mkdir()
    (tmp_path / "ufc-config.json").write_text('{"flags": {"one": {}}}', encoding="utf-8")
    (cases_directory / "first.json").write_text('[{"flag": "one"}]', encoding="utf-8")
    (cases_directory / "second.json").write_text('[{"flag": "two"}, {"flag": "three"}]', encoding="utf-8")
    _write_feature_suite(tmp_path)

    assert update_ffe_fixtures._validate_fixture_snapshot(tmp_path) == 4


@scenarios.test_the_test
def test_validate_fixture_snapshot_rejects_unexpected_feature_suite_entries(tmp_path: Path) -> None:
    cases_directory = tmp_path / "evaluation-cases"
    cases_directory.mkdir()
    (tmp_path / "ufc-config.json").write_text('{"flags": {"one": {}}}', encoding="utf-8")
    (cases_directory / "case.json").write_text('[{"flag": "one"}]', encoding="utf-8")
    _write_feature_suite(tmp_path)
    (tmp_path / "evaluation-suites" / "dependent-flags" / "README.md").write_text("unexpected", encoding="utf-8")

    with pytest.raises(ValueError, match="must contain only ufc-config.json and cases"):
        update_ffe_fixtures._validate_fixture_snapshot(tmp_path)


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


@scenarios.test_the_test
def test_update_fixtures_preserves_snapshot_on_validation_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "upstream"
    destination = tmp_path / "destination"
    (source / "evaluation-cases").mkdir(parents=True)
    (source / "ufc-config.json").write_text('{"flags": {"flag": {}}}', encoding="utf-8")
    (source / "evaluation-cases" / "case.json").write_text("[]", encoding="utf-8")
    _write_feature_suite(source)
    destination.mkdir()
    (destination / "SOURCE.md").write_text("original snapshot", encoding="utf-8")

    def fake_git(working_directory: Path, *arguments: str) -> str:
        if arguments[0] == "checkout":
            shutil.copytree(source, working_directory, dirs_exist_ok=True)
        return "a" * 40

    monkeypatch.setattr(update_ffe_fixtures, "_run_git", fake_git)
    monkeypatch.setattr(update_ffe_fixtures, "FIXTURE_DESTINATION", destination)
    with pytest.raises(ValueError, match="at least one evaluation case"):
        update_ffe_fixtures.update_fixtures("main")
    assert (destination / "SOURCE.md").read_text() == "original snapshot"


@scenarios.test_the_test
def test_update_fixtures_records_source_and_removes_stale_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "upstream"
    destination = tmp_path / "destination"
    output = tmp_path / "outputs"
    (source / "evaluation-cases").mkdir(parents=True)
    (source / "ufc-config.json").write_text('{"flags": {"flag": {}}}', encoding="utf-8")
    case_file = source / "evaluation-cases" / "case.json"
    case_file.write_text('[{"flag": "flag"}]', encoding="utf-8")
    _write_feature_suite(source)
    destination.mkdir()
    (destination / "stale.json").write_text("[]", encoding="utf-8")

    def fake_git(working_directory: Path, *arguments: str) -> str:
        if arguments[0] == "checkout":
            shutil.copytree(source, working_directory, dirs_exist_ok=True)
        return "a" * 40

    monkeypatch.setattr(update_ffe_fixtures, "_run_git", fake_git)
    monkeypatch.setattr(update_ffe_fixtures, "FIXTURE_DESTINATION", destination)
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    assert update_ffe_fixtures.update_fixtures("main")
    assert not (destination / "stale.json").exists()
    assert (destination / "evaluation-cases" / "case.json").read_bytes() == case_file.read_bytes()
    assert (destination / "evaluation-suites" / "dependent-flags" / "cases" / "dependent.json").is_file()
    metadata = (destination / "SOURCE.md").read_bytes()
    assert ("a" * 40).encode() in metadata
    assert "fixture_count=2\nchanged=true\n" in output.read_text()

    (source / "README.md").write_text("documentation-only upstream change", encoding="utf-8")
    assert not update_ffe_fixtures.update_fixtures("main")
    assert (destination / "SOURCE.md").read_bytes() == metadata
    assert output.read_text().endswith("changed=false\n")
