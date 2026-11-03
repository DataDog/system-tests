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


@scenarios.test_the_test
def test_copy_fixture_snapshot_imports_only_server_evaluator_data(tmp_path: Path) -> None:
    source = tmp_path / "source"
    snapshot = tmp_path / "snapshot"
    (source / "evaluation-cases").mkdir(parents=True)
    snapshot.mkdir()
    (source / "evaluation-cases" / "case.json").write_text("[]", encoding="utf-8")
    (source / "ufc-config.json").write_text("{}", encoding="utf-8")
    (source / "README.md").write_text("upstream documentation", encoding="utf-8")
    (source / "AGENTS.md").write_text("upstream instructions", encoding="utf-8")
    (source / "precomputed-assignments").mkdir()

    update_ffe_fixtures._copy_fixture_snapshot(source, snapshot)

    assert (snapshot / "ufc-config.json").is_file()
    assert (snapshot / "evaluation-cases" / "case.json").is_file()
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
    target = source / "target.json"
    target.write_text("{}", encoding="utf-8")
    (source / "evaluation-cases" / "linked.json").symlink_to(target)

    with pytest.raises(ValueError, match="Refusing to copy symbolic link"):
        update_ffe_fixtures._copy_fixture_snapshot(source, snapshot)


@scenarios.test_the_test
def test_copy_flag_selection_snapshot_imports_only_vectors(tmp_path: Path) -> None:
    source = tmp_path / "source"
    snapshot = tmp_path / "snapshot"
    (source / "flag-selection").mkdir(parents=True)
    snapshot.mkdir()
    (source / "flag-selection" / "selection-vectors.json").write_text('{"flags": [], "cases": []}', encoding="utf-8")
    (source / "flag-selection" / "README.md").write_text("upstream documentation", encoding="utf-8")

    update_ffe_fixtures._copy_flag_selection_snapshot(source, snapshot)
    update_ffe_fixtures._validate_flag_selection_snapshot(snapshot)

    assert [path.name for path in (snapshot / "flag-selection").iterdir()] == ["selection-vectors.json"]


@scenarios.test_the_test
def test_copy_flag_selection_snapshot_skips_absent_directory(tmp_path: Path) -> None:
    (tmp_path / "source").mkdir()
    (tmp_path / "snapshot").mkdir()

    update_ffe_fixtures._copy_flag_selection_snapshot(tmp_path / "source", tmp_path / "snapshot")
    update_ffe_fixtures._validate_flag_selection_snapshot(tmp_path / "snapshot")

    assert not (tmp_path / "snapshot" / "flag-selection").exists()


@scenarios.test_the_test
def test_copy_flag_selection_snapshot_requires_vectors(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "flag-selection").mkdir(parents=True)
    (source / "flag-selection" / "README.md").write_text("upstream documentation", encoding="utf-8")

    with pytest.raises(ValueError, match="must contain selection-vectors.json"):
        update_ffe_fixtures._copy_flag_selection_snapshot(source, tmp_path / "snapshot")


@scenarios.test_the_test
def test_copy_flag_selection_snapshot_rejects_symbolic_link_directory(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "flag-selection").symlink_to(target, target_is_directory=True)

    with pytest.raises(ValueError, match="Refusing to copy symbolic link"):
        update_ffe_fixtures._copy_flag_selection_snapshot(source, tmp_path / "snapshot")


@scenarios.test_the_test
def test_validate_flag_selection_snapshot_rejects_unexpected_fields(tmp_path: Path) -> None:
    (tmp_path / "flag-selection").mkdir()
    (tmp_path / "flag-selection" / "selection-vectors.json").write_text(
        '{"flags": [], "cases": [], "extra": 1}', encoding="utf-8"
    )

    with pytest.raises(ValueError, match="selection-vectors.json must contain only cases, flags"):
        update_ffe_fixtures._validate_flag_selection_snapshot(tmp_path)


def _write_suite(snapshot: Path) -> Path:
    (snapshot / "evaluation-cases").mkdir(parents=True)
    (snapshot / "ufc-config.json").write_text('{"flags": {"one": {}}}', encoding="utf-8")
    (snapshot / "evaluation-cases" / "case.json").write_text('[{"flag": "one"}]', encoding="utf-8")
    suite = snapshot / "evaluation-suites" / "flag-selection"
    (suite / "cases").mkdir(parents=True)
    (suite / "ufc-config.json").write_text('{"flags": {"two": {}}}', encoding="utf-8")
    (suite / "cases" / "tags.json").write_text('[{"flag": "two"}]', encoding="utf-8")
    return suite


@scenarios.test_the_test
def test_validate_fixture_snapshot_accepts_suite_flag_tags(tmp_path: Path) -> None:
    suite = _write_suite(tmp_path)
    (suite / "flag-tags.json").write_text('{"flags": [{"key": "two", "tags": ["team:checkout"]}]}', encoding="utf-8")

    assert update_ffe_fixtures._validate_fixture_snapshot(tmp_path) == 2


@scenarios.test_the_test
@pytest.mark.parametrize(
    ("name", "content", "message"),
    [
        ("flag-tags.json", '{"flags": {}}', "must contain only a flags array"),
        ("flag-tags.json", '{"flags": [], "extra": 1}', "must contain only a flags array"),
        ("notes.json", "{}", "must contain only ufc-config.json, cases and an optional flag-tags.json"),
    ],
)
def test_validate_fixture_snapshot_rejects_invalid_suite_entries(
    tmp_path: Path, name: str, content: str, message: str
) -> None:
    (_write_suite(tmp_path) / name).write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        update_ffe_fixtures._validate_fixture_snapshot(tmp_path)


@scenarios.test_the_test
def test_validate_fixture_snapshot_counts_evaluations(tmp_path: Path) -> None:
    cases_directory = tmp_path / "evaluation-cases"
    cases_directory.mkdir()
    (tmp_path / "ufc-config.json").write_text('{"flags": {"one": {}}}', encoding="utf-8")
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


@scenarios.test_the_test
def test_update_fixtures_preserves_snapshot_on_validation_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "upstream"
    destination = tmp_path / "destination"
    (source / "evaluation-cases").mkdir(parents=True)
    (source / "ufc-config.json").write_text('{"flags": {"flag": {}}}', encoding="utf-8")
    (source / "evaluation-cases" / "case.json").write_text("[]", encoding="utf-8")
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
    metadata = (destination / "SOURCE.md").read_bytes()
    assert ("a" * 40).encode() in metadata
    assert "fixture_count=1\nchanged=true\n" in output.read_text()

    (source / "README.md").write_text("documentation-only upstream change", encoding="utf-8")
    assert not update_ffe_fixtures.update_fixtures("main")
    assert (destination / "SOURCE.md").read_bytes() == metadata
    assert output.read_text().endswith("changed=false\n")
