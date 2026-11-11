"""Tests of the review-learning scripts in utils/scripts/review_learning. They never use the network."""

import subprocess
from datetime import date
from pathlib import Path

from utils import features, pytest, scenarios
from utils.scripts.review_learning import clean, collect, szz, thread_outcome
from utils.scripts.review_learning import filter as filter_step
from utils.scripts.review_learning.common import Json, load_filters, matches_any, read_json, write_json

FILTERS = load_filters()


def _author(login: str = "alice", kind: str = "User") -> Json:
    return {"login": login, "type": kind, "association": "MEMBER"}


def _comment(body: str, login: str = "alice", kind: str = "User", created_at: str = "2026-10-01T10:00:00Z") -> Json:
    return {"author": _author(login, kind), "body": body, "created_at": created_at, "url": None, "diff_hunk": None,
            "thumbs_up": 0, "thumbs_down": 0}  # fmt: skip


def _thread(*comments: Json, is_outdated: bool = False, is_resolved: bool = False) -> Json:
    return {"is_resolved": is_resolved, "is_outdated": is_outdated, "path": "tests/test_a.py", "line": 3,
            "original_line": 3, "comments": list(comments)}  # fmt: skip


def _pr(number: int = 1, title: str = "Add a test", login: str = "alice", kind: str = "User", **extra: object) -> Json:
    pr: Json = {"number": number, "title": title, "body": "", "url": "", "merged_at": "2026-10-02T00:00:00Z",
                "author": _author(login, kind), "labels": [], "merge_commit": None, "files": [], "commits": [],
                "reviews": [], "comments": [], "threads": []}  # fmt: skip
    return {**pr, **extra}


@features.not_reported
@scenarios.test_the_test
class Test_ReviewLearningCommon:
    def test_star_is_the_only_wildcard(self) -> None:
        assert matches_any("renovate[bot]", ["*[bot]"])
        assert not matches_any("claponcet", ["*[bot]"])
        assert matches_any("Auto-activate php easy wins for apm-lang-platform", ["Auto-activate * easy wins for *"])
        assert matches_any("LGTM", ["lgtm"])
        assert not matches_any("lgtm, but rename it", ["lgtm"])

    def test_write_json_reads_back(self, tmp_path: Path) -> None:
        path = tmp_path / "a" / "b.json"
        write_json(path, {"x": [1, "é"]})
        assert read_json(path) == {"x": [1, "é"]}


@features.not_reported
@scenarios.test_the_test
class Test_ReviewLearningCollect:
    def test_parse_window(self) -> None:
        today = date(2026, 11, 11)
        assert collect.parse_window("30d", today) == (date(2026, 10, 12), today)
        assert collect.parse_window("2026-10-01..2026-10-31", today) == (date(2026, 10, 1), date(2026, 10, 31))
        with pytest.raises(ValueError, match="ends before"):
            collect.parse_window("2026-10-31..2026-10-01", today)
        with pytest.raises(ValueError, match="must look like"):
            collect.parse_window("a month", today)

    def test_fetch_follows_pages(self) -> None:
        pages = [
            {"issueCount": 2, "pageInfo": {"hasNextPage": True, "endCursor": "c1"}, "nodes": [{"number": 1}]},
            {"issueCount": 2, "pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": [{"number": 2}]},
        ]
        calls: list[dict[str, str]] = []

        def graphql(_query: str, variables: dict[str, str]) -> Json:
            calls.append(variables)
            return {"data": {"search": pages[len(calls) - 1]}}

        nodes = collect.fetch_pull_requests("o/r", date(2026, 10, 1), date(2026, 10, 2), graphql)
        assert [node["number"] for node in nodes] == [1, 2]
        assert calls[0] == {"q": "repo:o/r is:pr is:merged merged:2026-10-01..2026-10-02"}
        assert calls[1]["after"] == "c1"

    def test_normalize_flattens_nodes(self) -> None:
        reactions = [{"content": "THUMBS_UP", "users": {"totalCount": 2}}]
        node = {
            "number": 7, "title": "t", "body": None, "url": "u", "mergedAt": "m", "author": None,
            "authorAssociation": None, "labels": {"nodes": [{"name": "x"}]}, "mergeCommit": {"oid": "abc"},
            "files": {"nodes": [{"path": "a.py", "additions": 1, "deletions": 0}]},
            "commits": {"nodes": [{"commit": {"oid": "c", "committedDate": "d", "messageHeadline": "h"}}]},
            "reviews": {"nodes": []}, "comments": {"nodes": []},
            "reviewThreads": {"nodes": [{"isResolved": True, "isOutdated": False, "path": "a.py", "line": 1,
                "originalLine": 1, "comments": {"nodes": [{"author": {"login": "bob", "__typename": "User"},
                "authorAssociation": "MEMBER", "body": "b", "createdAt": "t0", "url": "u2", "diffHunk": "@@",
                "reactionGroups": reactions}]}}]},
        }  # fmt: skip
        pr = collect.normalize(node)
        assert pr["author"] == {"login": "ghost", "type": "User", "association": None}
        assert pr["body"] == ""
        assert pr["labels"] == ["x"]
        assert pr["commits"] == [{"oid": "c", "date": "d", "headline": "h"}]
        assert pr["threads"][0]["comments"][0]["thumbs_up"] == 2
        assert pr["threads"][0]["comments"][0]["author"]["association"] == "MEMBER"


@features.not_reported
@scenarios.test_the_test
class Test_ReviewLearningFilter:
    def test_excludes_automated_pull_requests(self) -> None:
        assert (
            filter_step.exclusion_reason(_pr(login="dd-octo-sts", kind="Bot"), FILTERS)
            == "automated author dd-octo-sts"
        )
        assert filter_step.exclusion_reason(_pr(title="Update Agent to 7.85.3"), FILTERS) == "automated title"
        title = "Auto-activate php easy wins for apm-lang-platform"
        assert filter_step.exclusion_reason(_pr(title=title), FILTERS) == "automated title"
        assert filter_step.exclusion_reason(_pr(number=8278), FILTERS) == "listed in exclude_prs.numbers"
        assert filter_step.exclusion_reason(_pr(labels=["do-not-merge"]), FILTERS) == "label do-not-merge"
        assert filter_step.exclusion_reason(_pr(login="claponcet"), FILTERS) is None

    def test_drops_threads_opened_by_bots(self) -> None:
        codex = _thread(_comment("P1: bug", login="chatgpt-codex-connector", kind="Bot"), _comment("fixed"))
        assert filter_step.clean_thread(codex, [], FILTERS) is None

    def test_keeps_only_human_comments(self) -> None:
        thread = _thread(
            _comment("Store it in setup"), _comment("LGTM", login="bob"), _comment("x", login="datadog-prod-us1")
        )
        cleaned = filter_step.clean_thread(thread, [], FILTERS)
        assert cleaned is not None
        assert [c["body"] for c in cleaned["comments"]] == ["Store it in setup"]
        assert cleaned["outcome"] == thread_outcome.IGNORED

    def test_budget_drops_weakest_threads_first(self) -> None:
        applied = {**_thread(_comment("a" * 60)), "outcome": thread_outcome.APPLIED}
        ignored = {**_thread(_comment("b" * 60)), "outcome": thread_outcome.IGNORED}
        fitted = filter_step.fit_in_budget(_pr(threads=[ignored, applied]), max_chars=100)
        assert fitted["threads"] == [applied]
        assert fitted["dropped_threads"] == 1

    def test_filter_run_writes_both_files(self, tmp_path: Path) -> None:
        write_json(tmp_path / "evidence" / "1.json", _pr(1))
        write_json(tmp_path / "evidence" / "2.json", _pr(2, login="dd-octo-sts", kind="Bot"))
        kept, excluded = filter_step.filter_run(tmp_path, FILTERS)
        assert [pr["number"] for pr in kept] == [1]
        assert read_json(tmp_path / "excluded.json") == excluded
        assert excluded[0]["number"] == 2


@features.not_reported
@scenarios.test_the_test
class Test_ReviewLearningThreadOutcome:
    later_commit = [{"oid": "c", "date": "2026-10-02T00:00:00Z", "headline": "address review"}]

    def test_outcomes(self) -> None:
        opener = _comment("Do not assert in setup")
        cases = [
            (_thread(opener, _comment("I disagree, it is a prerequisite", login="bob")), [], thread_outcome.DISPUTED),
            (_thread(opener, is_outdated=True), self.later_commit, thread_outcome.APPLIED),
            (_thread(opener, is_outdated=True), [], thread_outcome.IGNORED),
            (_thread(opener, _comment("Done.", login="bob")), [], thread_outcome.APPLIED),
            (_thread(opener, _comment("fixed in 1a2b3c4d", login="bob")), [], thread_outcome.APPLIED),
            (_thread(opener, _comment("Why?", login="bob")), [], thread_outcome.DISCUSSED),
            (_thread(opener, is_resolved=True), [], thread_outcome.RESOLVED),
            (_thread(opener), [], thread_outcome.IGNORED),
        ]
        for thread, commits, expected in cases:
            assert thread_outcome.classify(thread, commits) == expected, thread

    def test_commit_before_the_comment_does_not_count(self) -> None:
        early = [{"oid": "c", "date": "2026-09-30T00:00:00Z", "headline": "first version"}]
        assert thread_outcome.classify(_thread(_comment("x"), is_outdated=True), early) == thread_outcome.IGNORED


def _git(root: Path, *args: str) -> str:
    command = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false", *args]
    return subprocess.run(command, cwd=root, check=True, capture_output=True, text=True).stdout.strip()


def _commit(root: Path, files: dict[str, str], message: str) -> str:
    for name, content in files.items():
        (root / name).write_text(content, encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", message)
    return _git(root, "rev-parse", "HEAD")


@features.not_reported
@scenarios.test_the_test
class Test_ReviewLearningSzz:
    def test_parse_diff(self) -> None:
        diff = """\
diff --git a/m.yml b/m.yml
--- a/m.yml
+++ b/m.yml
@@ -4,2 +4 @@
--- yaml start
-b
diff --git a/s.sh b/s.sh
--- a/s.sh
+++ b/s.sh
@@ -7,0 +8 @@
+set -e
diff --git a/new.py b/new.py
--- /dev/null
+++ b/new.py
@@ -0,0 +1 @@
+x = 1
"""
        assert szz.parse_diff(diff) == [
            szz.FileChange("m.yml", (4, 5), additions_only=False),
            szz.FileChange("s.sh", (7,), additions_only=True),
        ]

    def test_text_signals(self) -> None:
        assert szz.is_fix_candidate("fix(ffe): accept queries", "")
        assert szz.is_fix_candidate("Make it work", "Follow-up to #8143")
        assert szz.is_fix_candidate('Revert "x"', "Reverts DataDog/system-tests#8052")
        assert not szz.is_fix_candidate("Add a quick start", "Fixes the docs")
        assert szz.linked_prs("t", "regression from https://github.com/DataDog/system-tests/pull/12 and #13") == [12]
        assert szz.pr_from_subject("Enable DSM tests for PHP (#8202)") == 8202
        assert szz.pr_from_subject("Merge branch main") is None

    def test_blame_finds_the_culprit(self, tmp_path: Path) -> None:
        _git(tmp_path, "init", "-q")
        _commit(tmp_path, {"m.yml": "a\nb\nc\n"}, "Add manifest (#1)")
        _commit(tmp_path, {"m.yml": "a\nBAD\nc\n"}, "Activate a test (#2)")
        _commit(tmp_path, {"m.yml": "a\nBAD\nc\n", "README.md": "doc\n"}, "docs: update readme (#3)")
        sha = _commit(tmp_path, {"m.yml": "a\nGOOD\nc\n"}, "fix: deactivate the test (#4)")
        fix = szz.analyse_fix(_pr(4, title="fix: deactivate the test", merge_commit=sha), tmp_path, ())
        assert fix is not None
        assert [(c["pr"], c["signal"], c["blamed_lines"]) for c in fix["culprits"]] == [(2, "blame", 1)]
        assert fix["absence"] is False

    def test_revert_and_absence(self, tmp_path: Path) -> None:
        _git(tmp_path, "init", "-q")
        _commit(tmp_path, {"a.py": "x = 1\n"}, "Add a (#1)")
        _commit(tmp_path, {"a.py": "x = 1\ny = 2\n"}, "Add y (#2)")
        sha = _commit(tmp_path, {"a.py": "x = 1\n"}, 'Revert "Add y" (#3)')
        fix = szz.analyse_fix(_pr(3, title='Revert "Add y"', body="Reverts DataDog/system-tests#2", merge_commit=sha),
                              tmp_path, ())  # fmt: skip
        assert fix is not None
        assert fix["culprits"][0]["pr"] == 2
        assert fix["culprits"][0]["signal"] == "revert"
        _commit(tmp_path, {"a.py": "x = 1\n", "b.sh": "set -e\n"}, "Add b (#4)")
        sha = _commit(tmp_path, {"a.py": "import os\nx = 1\n", "b.sh": "set -e\n"}, "fix: import os (#5)")
        fix = szz.analyse_fix(_pr(5, title="fix: import os", merge_commit=sha), tmp_path, ())
        assert fix is not None
        assert fix["additions_only"] is True
        assert fix["absence"] is True

    def test_not_a_fix(self, tmp_path: Path) -> None:
        assert szz.analyse_fix(_pr(1, title="Add a test"), tmp_path, ()) is None


def _run_folder(root: Path, name: str, collected_at: str) -> Path:
    write_json(root / name / "index.json", {"collected_at": collected_at})
    return root / name


@features.not_reported
@scenarios.test_the_test
class Test_ReviewLearningClean:
    def test_keeps_the_newest_runs(self, tmp_path: Path) -> None:
        old = _run_folder(tmp_path, "a", "2026-09-01T00:00:00+00:00")
        new = _run_folder(tmp_path, "b", "2026-11-01T00:00:00+00:00")
        assert clean.clean(tmp_path, keep=1, dry_run=False) == [old]
        assert not old.exists()
        assert new.exists()

    def test_dry_run_deletes_nothing(self, tmp_path: Path) -> None:
        run = _run_folder(tmp_path, "a", "2026-09-01T00:00:00+00:00")
        assert clean.clean(tmp_path, keep=0, dry_run=True) == [run]
        assert run.exists()

    def test_deletes_only_run_folders(self, tmp_path: Path) -> None:
        (tmp_path / "notes").mkdir()
        (tmp_path / "file.json").write_text("{}", encoding="utf-8")
        target = _run_folder(tmp_path / "outside", "precious", "2026-09-01T00:00:00+00:00")
        (tmp_path / "link").symlink_to(target)
        assert clean.clean(tmp_path, keep=0, dry_run=False) == []
        assert (tmp_path / "notes").exists()
        assert target.exists()

    def test_missing_root_and_bad_keep(self, tmp_path: Path) -> None:
        assert clean.clean(tmp_path / "missing", keep=0, dry_run=False) == []
        with pytest.raises(ValueError, match="keep must be"):
            clean.clean(tmp_path, keep=-1, dry_run=False)

    def test_default_run_folder_uses_the_window(self) -> None:
        folder = collect.default_run_dir(date(2026, 10, 1), date(2026, 10, 31))
        assert folder == Path(".review-learning/2026-10-01..2026-10-31")
