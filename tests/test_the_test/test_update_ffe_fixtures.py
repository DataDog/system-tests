# ruff: noqa: SLF001

from pathlib import Path
import json
import shutil
from typing import Any

from utils import pytest

from utils import scenarios
from utils.scripts import update_ffe_fixtures

VALID_VECTORS = json.dumps(
    {
        "flags": [{"key": "one", "tags": []}],
        "cases": [
            {
                "name": "case",
                "query": {},
                "expected": {"outcome": "applied", "selectedKeys": ["one"]},
                "sdk": {"selection": {"tags": [], "keyPatterns": []}},
            }
        ],
    }
)


def _write_selection_vectors(root: Path, cases: list[dict[str, Any]] | None = None) -> None:
    path = root / update_ffe_fixtures.SELECTION_VECTORS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    if cases is None:
        cases = [
            {"name": "empty selection", "query": {}, "sdk": {"selection": {"tags": [], "keyPatterns": []}}},
            {"name": "raw query", "rawQuery": "selected_flag_tags=%zz"},
        ]
    for case in cases:
        if isinstance(case, dict):
            case.setdefault("expected", {"outcome": "applied", "selectedKeys": []})
    path.write_text(json.dumps({"flags": [{"key": "one", "tags": []}], "cases": cases}), encoding="utf-8")


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
def test_copy_fixture_snapshot_imports_only_consumed_fixture_data(tmp_path: Path) -> None:
    source = tmp_path / "source"
    snapshot = tmp_path / "snapshot"
    (source / "evaluation-cases").mkdir(parents=True)
    snapshot.mkdir()
    (source / "evaluation-cases" / "case.json").write_text("[]", encoding="utf-8")
    (source / "ufc-config.json").write_text("{}", encoding="utf-8")
    (source / "README.md").write_text("upstream documentation", encoding="utf-8")
    (source / "AGENTS.md").write_text("upstream instructions", encoding="utf-8")
    (source / "precomputed-assignments").mkdir()
    suite = source / "evaluation-suites" / "feature"
    (suite / "cases").mkdir(parents=True)
    (suite / "ufc-config.json").write_text('{"flags": {"flag": {}}}', encoding="utf-8")
    (suite / "cases" / "case.json").write_text('[{"flag": "flag"}]', encoding="utf-8")
    _write_selection_vectors(source)
    (source / "flag-selection" / "README.md").write_text("upstream documentation", encoding="utf-8")
    (source / "flag-selection" / "AGENTS.md").write_text("upstream instructions", encoding="utf-8")

    update_ffe_fixtures._copy_fixture_snapshot(source, snapshot)

    assert (snapshot / "ufc-config.json").is_file()
    assert (snapshot / "evaluation-cases" / "case.json").is_file()
    for path in (Path("ufc-config.json"), Path("cases/case.json")):
        assert (snapshot / "evaluation-suites" / "feature" / path).read_bytes() == (suite / path).read_bytes()
    assert not (snapshot / "README.md").exists()
    assert not (snapshot / "AGENTS.md").exists()
    assert not (snapshot / "precomputed-assignments").exists()
    assert (snapshot / update_ffe_fixtures.SELECTION_VECTORS_PATH).read_bytes() == (
        source / update_ffe_fixtures.SELECTION_VECTORS_PATH
    ).read_bytes()
    assert not (snapshot / "flag-selection" / "README.md").exists()
    assert not (snapshot / "flag-selection" / "AGENTS.md").exists()


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
@pytest.mark.parametrize("link_directory", [False, True], ids=["file", "directory"])
def test_copy_fixture_snapshot_rejects_selection_symbolic_links(tmp_path: Path, *, link_directory: bool) -> None:
    source = tmp_path / "source"
    snapshot = tmp_path / "snapshot"
    (source / "evaluation-cases").mkdir(parents=True)
    (source / "ufc-config.json").write_text("{}", encoding="utf-8")
    target = tmp_path / "target"
    _write_selection_vectors(target)
    if link_directory:
        (source / "flag-selection").symlink_to(target / "flag-selection", target_is_directory=True)
    else:
        (source / "flag-selection").mkdir()
        (source / update_ffe_fixtures.SELECTION_VECTORS_PATH).symlink_to(
            target / update_ffe_fixtures.SELECTION_VECTORS_PATH
        )
    with pytest.raises(ValueError, match="Refusing to copy symbolic link"):
        update_ffe_fixtures._copy_fixture_snapshot(source, snapshot)


@scenarios.test_the_test
def test_validate_selection_vectors_rejects_what_the_mock_tests_cannot_read(tmp_path: Path) -> None:
    vectors = tmp_path / update_ffe_fixtures.SELECTION_VECTORS_PATH
    vectors.parent.mkdir()
    case = {"name": "case", "query": {}, "sdk": {"selection": {"tags": [], "keyPatterns": []}}}
    for content, message in (
        ({"cases": [{**case, "expected": {"outcome": "applied"}}]}, "flags must be a non-empty array"),
        (
            {"flags": [{"key": "one", "tags": [1]}], "cases": [{**case, "expected": {"outcome": "applied"}}]},
            "flags must be a non-empty array",
        ),
        ({"flags": [{"key": "one", "tags": []}], "cases": [case]}, "applied or ignored expected outcome"),
        ({"flags": [{"key": "one", "tags": []}], "cases": [{**case, "expected": {}}]}, "applied or ignored"),
    ):
        vectors.write_text(json.dumps(content), encoding="utf-8")
        with pytest.raises(ValueError, match=message):
            update_ffe_fixtures._validate_selection_vectors(tmp_path)


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
        ("flag-tags.json", '{"flags": {}}', "flags must be a non-empty array of key and tags entries"),
        ("flag-tags.json", '{"flags": [{"key": "two"}]}', "flags must be a non-empty array of key and tags entries"),
        ("flag-tags.json", '{"flags": [], "extra": 1}', "must contain only flags"),
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
def test_validate_selection_vectors_counts_only_sdk_cases(tmp_path: Path) -> None:
    _write_selection_vectors(tmp_path)
    assert update_ffe_fixtures._validate_selection_vectors(tmp_path) == 1


@scenarios.test_the_test
@pytest.mark.parametrize(
    ("cases", "message"),
    [
        ([], "non-empty cases array"),
        ([{"name": "raw", "rawQuery": ""}], "No FFE selection SDK cases"),
        ([{"query": {}}], "non-empty name"),
        ([{"name": "no query"}], "exactly one query form"),
        ([{"name": "both", "query": {}, "rawQuery": ""}], "exactly one query form"),
        ([{"name": "missing SDK expectation", "query": {}}], "one SDK expectation"),
        ([{"name": "raw with SDK expectation", "rawQuery": "", "sdk": {}}], "must not have an SDK expectation"),
        ([{"name": "invalid query", "query": {"selected_flag_tags": "web"}}], "Invalid FFE selection vector query"),
        ([{"name": "invalid item", "query": {"selected_flag_tags": [1]}}], "Invalid FFE selection vector query"),
        ([{"name": "unknown reason", "query": {}, "sdk": {"dropped": "unknown"}}], "Unknown FFE selection drop reason"),
        (
            [{"name": "both expectations", "query": {}, "sdk": {"dropped": "invalid_tag", "selection": {}}}],
            "one SDK expectation",
        ),
        (
            [{"name": "missing lists", "query": {}, "sdk": {"selection": {}}}],
            "Invalid canonical FFE selection expectation",
        ),
        (
            [{"name": "empty value", "query": {}, "sdk": {"selection": {"tags": [""], "keyPatterns": []}}}],
            "Invalid canonical FFE selection expectation",
        ),
        (
            [{"name": "duplicate", "query": {}, "sdk": {"dropped": "invalid_tag"}}] * 2,
            "Duplicate FFE selection vector name",
        ),
    ],
)
def test_validate_selection_vectors_rejects_invalid_cases(
    tmp_path: Path, cases: list[dict[str, Any]], message: str
) -> None:
    _write_selection_vectors(tmp_path, cases)
    with pytest.raises(ValueError, match=message):
        update_ffe_fixtures._validate_selection_vectors(tmp_path)


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
@pytest.mark.parametrize("invalid_selection", [False, True], ids=["evaluation", "selection"])
def test_update_fixtures_preserves_snapshot_on_validation_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, invalid_selection: bool
) -> None:
    source = tmp_path / "upstream"
    destination = tmp_path / "destination"
    (source / "evaluation-cases").mkdir(parents=True)
    (source / "ufc-config.json").write_text('{"flags": {"flag": {}}}', encoding="utf-8")
    (source / "evaluation-cases" / "case.json").write_text(
        '[{"flag": "flag"}]' if invalid_selection else "[]", encoding="utf-8"
    )
    _write_selection_vectors(source, [] if invalid_selection else None)
    destination.mkdir()
    (destination / "SOURCE.md").write_text("original snapshot", encoding="utf-8")

    def fake_git(working_directory: Path, *arguments: str) -> str:
        if arguments[0] == "checkout":
            shutil.copytree(source, working_directory, dirs_exist_ok=True)
        return "a" * 40

    monkeypatch.setattr(update_ffe_fixtures, "_run_git", fake_git)
    monkeypatch.setattr(update_ffe_fixtures, "FIXTURE_DESTINATION", destination)
    with pytest.raises(
        ValueError, match="non-empty cases array" if invalid_selection else "at least one evaluation case"
    ):
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
    _write_selection_vectors(source)
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
    assert "fixture_count=1\nselection_fixture_count=1\nchanged=true\n" in output.read_text()

    (source / "README.md").write_text("documentation-only upstream change", encoding="utf-8")
    assert not update_ffe_fixtures.update_fixtures("main")
    assert (destination / "SOURCE.md").read_bytes() == metadata
    assert output.read_text().endswith("changed=false\n")

    _write_selection_vectors(source, [{"name": "new SDK case", "query": {}, "sdk": {"dropped": "invalid_tag"}}])
    assert update_ffe_fixtures.update_fixtures("main")
    assert (destination / update_ffe_fixtures.SELECTION_VECTORS_PATH).read_bytes() == (
        source / update_ffe_fixtures.SELECTION_VECTORS_PATH
    ).read_bytes()
    assert (destination / "evaluation-cases" / "case.json").read_bytes() == case_file.read_bytes()


@scenarios.test_the_test
def test_update_fixtures_vendors_and_checks_selection_vectors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "upstream"
    destination = tmp_path / "destination"
    _write_suite(source)
    (source / "flag-selection").mkdir()
    (source / "flag-selection" / "selection-vectors.json").write_text(VALID_VECTORS, encoding="utf-8")
    (source / "flag-selection" / "README.md").write_text("upstream documentation", encoding="utf-8")
    destination.mkdir()

    def fake_git(working_directory: Path, *arguments: str) -> str:
        if arguments[0] == "checkout":
            shutil.copytree(source, working_directory, dirs_exist_ok=True)
        return "a" * 40

    monkeypatch.setattr(update_ffe_fixtures, "_run_git", fake_git)
    monkeypatch.setattr(update_ffe_fixtures, "FIXTURE_DESTINATION", destination)
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "outputs"))
    assert update_ffe_fixtures.update_fixtures("main")
    assert [path.name for path in (destination / "flag-selection").iterdir()] == ["selection-vectors.json"]

    invalid = json.loads(VALID_VECTORS) | {"flags": []}
    (source / "flag-selection" / "selection-vectors.json").write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(ValueError, match="flags must be a non-empty array"):
        update_ffe_fixtures.update_fixtures("main")
    assert (destination / "flag-selection" / "selection-vectors.json").read_text(encoding="utf-8") == VALID_VECTORS
