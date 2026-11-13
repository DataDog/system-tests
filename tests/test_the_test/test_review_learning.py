"""Tests of the review-learning scripts in utils/scripts/review_learning. They never use the network."""

import subprocess
from datetime import date
from pathlib import Path

from utils import features, pytest, scenarios
from utils.scripts.review_learning import (
    address,
    clean,
    collect,
    decide,
    plain_english,
    prepare,
    szz,
    thread_outcome,
    verify_quotes,
)
from utils.scripts.review_learning import apply as apply_step
from utils.scripts.review_learning import open_pr
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
        assert collect.parse_window("30d", today) == (date(2026, 10, 13), today)
        assert collect.parse_window("1d", today) == (today, today)
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

    def test_collect_replaces_old_evidence(self, tmp_path: Path) -> None:
        write_json(tmp_path / "evidence" / "99.json", {"number": 99})

        def graphql(_query: str, _variables: dict[str, str]) -> Json:
            page = {"issueCount": 0, "pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": []}
            return {"data": {"search": page}}

        collect.collect("o/r", date(2026, 10, 1), date(2026, 10, 2), tmp_path, graphql)
        assert not (tmp_path / "evidence" / "99.json").exists()
        assert read_json(tmp_path / "index.json")["pull_requests"] == []

    def test_normalize_flattens_nodes(self) -> None:
        reactions = [{"content": "THUMBS_UP", "users": {"totalCount": 2}}]
        node = {
            "number": 7, "title": "t", "body": None, "url": "u", "mergedAt": "m", "author": None,
            "authorAssociation": None, "labels": {"totalCount": 1, "nodes": [{"name": "x"}]}, "mergeCommit": {"oid": "abc"},
            "files": {"totalCount": 150, "nodes": [{"path": "a.py", "additions": 1, "deletions": 0}]},
            "commits": {"totalCount": 1, "nodes": [{"commit": {"oid": "c", "committedDate": "d", "messageHeadline": "h"}}]},
            "reviews": {"totalCount": 0, "nodes": []}, "comments": {"totalCount": 0, "nodes": []},
            "reviewThreads": {"totalCount": 1, "nodes": [{"isResolved": True, "isOutdated": False, "path": "a.py", "line": 1,
                "originalLine": 1, "comments": {"totalCount": 1, "nodes": [{"author": {"login": "bob", "__typename": "User"},
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
        assert pr["truncated"] == ["files"]


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

    def test_keeps_real_reviews_that_start_with_a_polite_word(self) -> None:
        thread = _thread(
            _comment("Nice idea, but this setup has no test"), _comment("Thanks, fixed in 1a2b3c4", login="bob")
        )
        cleaned = filter_step.clean_thread(thread, [], FILTERS)
        assert cleaned is not None
        assert len(cleaned["comments"]) == 2
        assert cleaned["outcome"] == thread_outcome.APPLIED

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

    def test_unintended_is_not_a_dispute(self) -> None:
        thread = _thread(_comment("x"), _comment("Good catch, that was unintended. Fixed in 1a2b3c4", login="bob"))
        assert thread_outcome.classify(thread, []) == thread_outcome.APPLIED

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
        assert szz.is_fix_candidate("[php] Fix Laravel 11 builds", "")
        assert szz.is_fix_candidate("AWS SSI: fix CentOS 7 Docker install", "")
        assert szz.is_fix_candidate("test(otel): fix gRPC assertion", "")
        assert not szz.is_fix_candidate("test(debugger): enable fixed Go and Java tests", "")
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

    def test_non_semantic_subjects(self) -> None:
        assert szz.NON_SEMANTIC.search("docs: update readme (#3)")
        assert szz.NON_SEMANTIC.search("chore(ci)!: bump runner (#4)")
        assert not szz.NON_SEMANTIC.search("[java] Fix spring-boot build for new version (#8123)")

    def test_parse_blame_uses_the_line_in_the_blamed_commit(self) -> None:
        porcelain = "a" * 40 + " 12 3 1\nauthor t\nfilename old/m.yml\n\tline\n"
        assert szz.parse_blame(porcelain) == ("a" * 40, 12, "old/m.yml")

    def test_unknown_culprit_files_give_no_absence(self) -> None:
        changes = [szz.FileChange("a.py", (1,), additions_only=False)]
        assert szz.absence(changes, {"files": []})["absence"] is False
        assert szz.absence(changes, {"files": ["b.py"]})["missing_in_culprit"] == ["a.py"]

    def test_blame_gives_no_culprit_after_only_non_semantic_hops(self, tmp_path: Path) -> None:
        _git(tmp_path, "init", "-q")
        _commit(tmp_path, {"m.yml": "a\n"}, "Add manifest (#1)")
        for number in range(2, 2 + szz.MAX_HOPS):
            _commit(tmp_path, {"m.yml": f"a{number}\n"}, f"docs: reword (#{number})")
        sha = _commit(tmp_path, {"m.yml": "fixed\n"}, "fix: manifest (#99)")
        assert szz.blame_line(sha, "m.yml", 1, tmp_path) is None
        assert szz.blame_line(f"{sha}~{szz.MAX_HOPS - 1}", "m.yml", 1, tmp_path) is not None

    def test_missing_merge_commit_is_reported(self, tmp_path: Path) -> None:
        _git(tmp_path, "init", "-q")
        _commit(tmp_path, {"a.py": "x\n"}, "Add a (#1)")
        fix = szz.analyse_fix(_pr(2, title="fix: a", merge_commit="f" * 40), tmp_path, ())
        assert fix is not None
        assert fix["error"].startswith("merge commit not found locally")

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

    def test_refuses_a_symlinked_root(self, tmp_path: Path) -> None:
        target = _run_folder(tmp_path / "outside", "precious", "2026-09-01T00:00:00+00:00")
        (tmp_path / "root").symlink_to(target.parent)
        with pytest.raises(ValueError, match="symbolic link"):
            clean.clean(tmp_path / "root", keep=0, dry_run=False)
        assert target.exists()

    def test_missing_root_and_bad_keep(self, tmp_path: Path) -> None:
        assert clean.clean(tmp_path / "missing", keep=0, dry_run=False) == []
        with pytest.raises(ValueError, match="keep must be"):
            clean.clean(tmp_path, keep=-1, dry_run=False)

    def test_default_run_folder_uses_the_window(self) -> None:
        folder = collect.default_run_dir(date(2026, 10, 1), date(2026, 10, 31))
        assert folder == Path(".review-learning/2026-10-01..2026-10-31")


def _write_run(root: Path, prs: list[Json], fixes: list[Json] | None = None) -> None:
    write_json(root / "index.json", {"start": "2026-10-01", "end": "2026-10-31", "pull_requests": prs})
    write_json(root / "filtered.json", prs)
    write_json(root / "fixes.json", fixes or [])


def _human_pr() -> Json:
    opener = {**_comment("You must store the response in setup, not assert there."), "url": "u1"}
    reply = {**_comment("> You must store\nDone, thanks", login="bob"), "url": "u2"}
    thread = {**_thread(opener, reply), "outcome": thread_outcome.APPLIED}
    return _pr(10, login="carol", threads=[thread], merge_commit=None)


@features.not_reported
@scenarios.test_the_test
class Test_ReviewLearningPrepare:
    def test_keeps_only_pull_requests_with_a_signal(self, tmp_path: Path) -> None:
        _write_run(tmp_path, [_human_pr(), _pr(11)])
        manifest = prepare.prepare(tmp_path, tmp_path)
        assert [batch["prs"] for batch in manifest["batches"]] == [[10]]
        text = (tmp_path / "batches" / "batch-01.txt").read_text(encoding="utf-8")
        assert text.startswith(f"<untrusted_pr_data_{manifest['nonce']}>\n")
        assert text.rstrip().endswith(f"</untrusted_pr_data_{manifest['nonce']}>")
        assert '"outcome": "applied"' in text

    def test_new_batches_delete_stale_model_outputs(self, tmp_path: Path) -> None:
        _write_run(tmp_path, [_human_pr()])
        write_json(tmp_path / "candidates" / "batch-03.json", {"candidates": []})
        write_json(tmp_path / "verified.json", [])
        prepare.prepare(tmp_path, tmp_path)
        assert not (tmp_path / "candidates" / "batch-03.json").exists()
        assert not (tmp_path / "verified.json").exists()

    def test_nonce_changes_on_each_run(self, tmp_path: Path) -> None:
        _write_run(tmp_path, [_human_pr()])
        assert prepare.prepare(tmp_path, tmp_path)["nonce"] != prepare.prepare(tmp_path, tmp_path)["nonce"]


@features.not_reported
@scenarios.test_the_test
class Test_ReviewLearningVerify:
    def _verify(
        self, tmp_path: Path, candidates: list[Json], fixes: list[Json] | None = None
    ) -> tuple[list[Json], list[Json]]:
        _write_run(tmp_path, [_human_pr()], fixes)
        write_json(
            tmp_path / "batches" / "manifest.json", {"nonce": "n", "batches": [{"file": "batch-01.txt", "prs": [10]}]}
        )
        write_json(tmp_path / "candidates" / "batch-01.json", {"candidates": candidates})
        write_json(
            tmp_path / "candidates" / "batch-09.json", {"candidates": [{"id": "old", "pr": 10, "signal": "miss"}]}
        )
        return verify_quotes.verify_run(tmp_path)

    def test_literal_quote_is_verified_and_author_comes_from_data(self, tmp_path: Path) -> None:
        candidate = {"id": "10-1", "pr": 10, "signal": "correction", "comment_url": "u1", "author": "made-up",
                     "quote": "store the  response in SETUP"}  # fmt: skip
        verified, unverified = self._verify(tmp_path, [candidate])
        assert unverified == []
        assert verified[0]["author"] == "alice"
        assert verified[0]["association"] == "MEMBER"
        assert verified[0]["outcome"] == thread_outcome.APPLIED

    def test_quoted_lines_are_not_the_author_s_words(self, tmp_path: Path) -> None:
        candidate = {"id": "10-1", "pr": 10, "signal": "correction", "comment_url": "u2", "quote": "You must store"}
        verified, unverified = self._verify(tmp_path, [candidate])
        assert verified == []
        assert unverified[0]["reason"] == "quote is not a literal part of the comment"

    def test_rejects_unknown_url_short_quote_and_bad_culprit(self, tmp_path: Path) -> None:
        fixes = [{"fix_pr": 10, "culprits": [{"pr": 4}], "absence": False}]
        candidates = [
            {"id": "a", "pr": 10, "signal": "correction", "comment_url": "nope", "quote": "store the response"},
            {"id": "b", "pr": 10, "signal": "correction", "comment_url": "u1", "quote": "store"},
            {"id": "c", "pr": 10, "signal": "miss", "culprit_pr": 5},
            {"id": "d", "pr": 10, "signal": "absence", "culprit_pr": 4},
            {"id": "e", "pr": 10, "signal": "miss", "culprit_pr": 4},
            {"id": "f", "pr": 10, "signal": "guess"},
            {"id": "g", "signal": "miss", "culprit_pr": 4},
            {"id": "h", "pr": "10", "signal": "miss", "culprit_pr": 4},
        ]
        verified, unverified = self._verify(tmp_path, candidates, fixes)
        assert [c["id"] for c in verified] == ["e"]
        assert [c["id"] for c in unverified] == ["a", "b", "c", "d", "f", "g", "h"]

    def test_author_of_the_pull_request_cannot_correct_it(self, tmp_path: Path) -> None:
        candidate = {"id": "10-1", "pr": 10, "signal": "correction", "comment_url": "u1", "quote": "store the response"}
        pr = {**_human_pr(), "author": _author("alice")}
        _write_run(tmp_path, [pr])
        write_json(
            tmp_path / "batches" / "manifest.json", {"nonce": "n", "batches": [{"file": "batch-01.txt", "prs": [10]}]}
        )
        write_json(tmp_path / "candidates" / "batch-01.json", {"candidates": [candidate]})
        _, unverified = verify_quotes.verify_run(tmp_path)
        assert unverified[0]["reason"].startswith("a correction must come from a reviewer")


@features.not_reported
@scenarios.test_the_test
class Test_ReviewLearningPlainEnglish:
    def test_lints_each_proposed_text(self, tmp_path: Path) -> None:
        proposals = [
            {"proposed_text": "You should wait."},
            {"proposed_text": "Wait for the trace."},
            {"action": "covered"},
        ]
        write_json(tmp_path / "proposals" / "lens.json", {"lens": "lens", "proposals": proposals})

        def linter(text: str) -> list[Json]:
            return [{"rule": "SE_MODAL_RESTRICTED", "message": "should"}] if "should" in text else []

        findings = plain_english.lint_run(tmp_path, linter)
        assert findings == {
            plain_english.proposal_key("lens", "You should wait."): [
                {"rule": "SE_MODAL_RESTRICTED", "message": "should"}
            ],
            plain_english.proposal_key("lens", "Wait for the trace."): [],
        }


LENS_TEXT = "### LIFE-001: Setup Methods Must Not Fail\n- Severity: P0\n- Flag: Do not assert in setup.\n- Detect: A setup method asserts.\n"


def _decide_root(tmp_path: Path) -> Path:
    lenses = tmp_path / "repo" / ".agents" / "rules" / "code-review"
    lenses.mkdir(parents=True)
    for lens, prefix in decide.LENS_PREFIX.items():
        text = LENS_TEXT if prefix == "LIFE" else f"### {prefix}-001: A rule\n- Severity: P1\n- Flag: A flag.\n"
        (lenses / f"{lens}.md").write_text(text, encoding="utf-8")
    (tmp_path / "repo" / "docs").mkdir()
    (tmp_path / "repo" / "docs" / "flushing.md").write_text("decision", encoding="utf-8")
    return tmp_path / "repo"


def _new_rule(rule_id: str, title: str = "Match the reply") -> str:
    return f"### {rule_id}: {title}\n- Severity: P1\n- Flag: Match the request id."


def _candidate(cid: str, pr: int, signal: str, association: str = "CONTRIBUTOR", outcome: str = "applied") -> Json:
    return {"id": cid, "pr": pr, "signal": signal, "association": association, "outcome": outcome, "quote": "q"}


@features.not_reported
@scenarios.test_the_test
class Test_ReviewLearningDecide:
    sharpen: Json = {
        "action": "sharpen",
        "rule_id": "LIFE-001",
        "field": "Detect",
        "current_text": "A setup method asserts.",
        "proposed_text": "A setup method asserts or raises.",
        "reason": "r",
    }

    def _decide(
        self, tmp_path: Path, proposals: list[Json], candidates: list[Json], max_changes: int = 5
    ) -> list[Json]:
        root = _decide_root(tmp_path)
        run = tmp_path / "run"
        _write_run(run, [])
        write_json(run / "verified.json", candidates)
        write_json(
            run / "proposals" / "lifecycle-and-isolation.json",
            {"lens": "lifecycle-and-isolation", "proposals": proposals},
        )
        plain_english.lint_run(run, lambda _text: [])
        return decide.decide_run(run, root, max_changes)

    def _statuses(
        self, tmp_path: Path, proposals: list[Json], candidates: list[Json], max_changes: int = 5
    ) -> list[str]:
        return [d["status"] for d in self._decide(tmp_path, proposals, candidates, max_changes)]

    def test_evidence_thresholds(self, tmp_path: Path) -> None:
        cases = [
            ([_candidate("a", 1, "miss")], decide.APPLY),
            ([_candidate("a", 1, "correction", association="MEMBER")], decide.APPLY),
            ([_candidate("a", 1, "correction")], decide.NOT_ENOUGH),
            ([_candidate("a", 1, "correction"), _candidate("b", 2, "correction")], decide.APPLY),
            ([_candidate("a", 1, "correction", association="MEMBER", outcome="discussed")], decide.NOT_ENOUGH),
            ([_candidate("a", 1, "human_only")], decide.NOT_ENOUGH),
            ([_candidate("a", 1, "disagreement"), _candidate("b", 2, "disagreement")], decide.NOT_ENOUGH),
        ]
        for index, (candidates, expected) in enumerate(cases):
            proposal = {**self.sharpen, "candidate_ids": [c["id"] for c in candidates]}
            assert self._statuses(tmp_path / str(index), [proposal], candidates) == [expected], candidates

    def test_add_not_when_needs_two_prs_or_a_written_decision(self, tmp_path: Path) -> None:
        one = [_candidate("a", 1, "disagreement")]
        base = {
            **self.sharpen,
            "action": "add_not_when",
            "field": "Not when",
            "current_text": None,
            "candidate_ids": ["a"],
        }
        assert self._statuses(tmp_path / "1", [base], one) == [decide.NOT_ENOUGH]
        cited = {**base, "cited_path": "docs/flushing.md"}
        assert self._statuses(tmp_path / "2", [cited], one) == [decide.APPLY]
        two = [*one, _candidate("b", 2, "disagreement")]
        assert self._statuses(tmp_path / "3", [{**base, "candidate_ids": ["a", "b"]}], two) == [decide.APPLY]

    def test_invalid_proposals(self, tmp_path: Path) -> None:
        miss = [_candidate("a", 1, "miss")]
        proposals: list[Json] = [
            {**self.sharpen, "rule_id": "LIFE-999", "candidate_ids": ["a"]},
            {**self.sharpen, "current_text": "text that is not in the lens", "candidate_ids": ["a"]},
            {"action": "new_rule", "rule_id": "TEST-005", "severity": "P0", "candidate_ids": ["a"]},
            {"action": "new_rule", "rule_id": "LIFE-001", "severity": "P0", "candidate_ids": ["a"]},
            {"action": "new_rule", "rule_id": "LIFE-005", "severity": "P2", "candidate_ids": ["a"]},
            {"action": "rewrite", "candidate_ids": ["a"]},
            {**self.sharpen, "current_text": None, "candidate_ids": ["a"]},
            {**self.sharpen, "proposed_text": None, "candidate_ids": ["a"]},
            {**self.sharpen, "field": "Ref", "candidate_ids": ["a"]},
        ]
        assert self._statuses(tmp_path, proposals, miss) == [decide.INVALID] * len(proposals)

    def test_decide_refuses_what_apply_would_refuse(self, tmp_path: Path) -> None:
        miss = [_candidate("a", 1, "miss")]
        proposals: list[Json] = [
            {**self.sharpen, "current_text": "A setup method", "candidate_ids": ["a"]},
            {**self.sharpen, "action": "add_not_when", "candidate_ids": ["a"]},
            {
                "action": "new_rule",
                "rule_id": "LIFE-005",
                "severity": "P0",
                "proposed_text": _new_rule("LIFE-005"),
                "candidate_ids": ["a"],
            },
            {
                "action": "new_rule",
                "rule_id": "LIFE-005",
                "severity": "P1",
                "proposed_text": "Match it.",
                "candidate_ids": ["a"],
            },
        ]
        decisions = self._decide(tmp_path, proposals, miss)
        assert [d["status"] for d in decisions] == [decide.INVALID] * len(proposals)
        assert "appears 0 times in the rule" in decisions[0]["status_reason"]

    def test_two_new_rules_cannot_share_an_id(self, tmp_path: Path) -> None:
        rule = {
            "action": "new_rule",
            "rule_id": "LIFE-005",
            "severity": "P1",
            "proposed_text": _new_rule("LIFE-005"),
            "candidate_ids": ["a"],
        }
        statuses = self._statuses(
            tmp_path,
            [rule, {**rule, "proposed_text": _new_rule("LIFE-005", "Another title")}],
            [_candidate("a", 1, "miss")],
        )
        assert statuses == [decide.APPLY, decide.INVALID]

    def test_unknown_lens_is_invalid(self, tmp_path: Path) -> None:
        root = _decide_root(tmp_path)
        run = tmp_path / "run"
        _write_run(run, [])
        write_json(run / "verified.json", [_candidate("a", 1, "miss")])
        write_json(
            run / "proposals" / "x.json", {"lens": "Lifecycle", "proposals": [{**self.sharpen, "candidate_ids": ["a"]}]}
        )
        assert decide.decide_run(run, root, 5)[0]["status_reason"] == "unknown lens Lifecycle"

    def test_new_rule_and_report_actions(self, tmp_path: Path) -> None:
        miss = [_candidate("a", 20, "miss")]
        proposals = [
            {
                "action": "new_rule",
                "rule_id": "LIFE-005",
                "severity": "P1",
                "proposed_text": _new_rule("LIFE-005"),
                "candidate_ids": ["a"],
            },
            {"action": "covered", "rule_id": "LIFE-001", "candidate_ids": ["a"]},
            {"action": "contested", "rule_id": "LIFE-001", "candidate_ids": ["a"]},
        ]
        statuses = self._statuses(tmp_path, proposals, miss)
        assert statuses == [decide.APPLY, decide.REPORT_ONLY, decide.NEEDS_DECISION]

    def test_lint_findings_block_the_change(self, tmp_path: Path) -> None:
        root = _decide_root(tmp_path)
        run = tmp_path / "run"
        _write_run(run, [])
        write_json(run / "verified.json", [_candidate("a", 1, "miss")])
        proposal = {**self.sharpen, "candidate_ids": ["a"]}
        write_json(run / "proposals" / "l.json", {"lens": "lifecycle-and-isolation", "proposals": [proposal]})
        key = plain_english.proposal_key("lifecycle-and-isolation", proposal["proposed_text"])
        write_json(run / "lint.json", {key: [{"rule": "SE_NO_SEMICOLON", "message": ";"}]})
        decision = decide.decide_run(run, root, 5)[0]
        assert decision["status"] == decide.NEEDS_DECISION
        assert "SE_NO_SEMICOLON" in decision["status_reason"]
        (run / "lint.json").unlink()
        decision = decide.decide_run(run, root, 5)[0]
        assert decision["status_reason"] == "plain_english.py did not lint this text"

    def test_cap_keeps_the_strongest_changes(self, tmp_path: Path) -> None:
        candidates = [_candidate("a", 1, "correction"), _candidate("b", 2, "correction"), _candidate("m", 3, "miss")]
        weak = {**self.sharpen, "candidate_ids": ["a", "b"]}
        strong = {**self.sharpen, "candidate_ids": ["m"]}
        assert self._statuses(tmp_path, [weak, strong], candidates, max_changes=1) == [decide.OVER_CAP, decide.APPLY]

    def test_report_is_complete_when_every_lens_answered(self, tmp_path: Path) -> None:
        run = tmp_path / "run"
        for lens in decide.LENS_PREFIX:
            if lens != "lifecycle-and-isolation":
                write_json(run / "proposals" / f"{lens}.json", {"lens": lens, "proposals": []})
        self._decide(tmp_path, [], [])
        text = (run / "report.md").read_text(encoding="utf-8")
        assert "Run incomplete" not in text
        assert "- test-effectiveness: 0 proposals" in text

    def test_report_lists_each_section(self, tmp_path: Path) -> None:
        candidates = [_candidate("a", 1, "miss"), {**_candidate("h", 2, "human_only"), "defect": "split it"}]
        self._decide(tmp_path, [{**self.sharpen, "candidate_ids": ["a"]}], candidates)
        text = (tmp_path / "run" / "report.md").read_text(encoding="utf-8")
        assert "# Review learning: 2026-10-01 to 2026-10-31" in text
        assert "### LIFE-001 · `sharpen` · lifecycle-and-isolation" in text
        assert "> A setup method asserts or raises." in text
        assert "## Human-only review and outside context" in text
        assert "- test-effectiveness: no output" in text
        assert "- lifecycle-and-isolation: 1 proposals" in text
        assert "**Run incomplete**: no output from test-effectiveness" in text
        assert "| Fixes that szz.py could not analyse | 0 |" in text


LENS = """### LIFE-001: Setup Methods Must Not Fail
- Severity: P0
- Flag: Do not assert in setup.
- Detect: A setup method asserts.
- Ref: [doc](x.md)

### LIFE-002: Avoid fixed sleeps
- Severity: P1
- Flag: Do not sleep.
- Not when: The delay is the behavior under test.
"""


def _edit(**extra: object) -> Json:
    return {"lens": "lifecycle-and-isolation", "action": "sharpen", "rule_id": "LIFE-001", "field": "Detect",
            "current_text": "A setup method asserts.", "proposed_text": "A setup method asserts or raises.", **extra}  # fmt: skip


@features.not_reported
@scenarios.test_the_test
class Test_ReviewLearningApply:
    def test_edit_replaces_one_field_line(self) -> None:
        text = apply_step.apply_one(LENS, _edit())
        assert "- Detect: A setup method asserts or raises.\n" in text
        assert "- Detect: A setup method asserts.\n" not in text
        assert text.count("### ") == 2

    def test_add_not_when_inserts_the_field(self) -> None:
        decision = _edit(action="add_not_when", field="Not when", current_text=None, proposed_text="It is parametric.")
        lines = apply_step.apply_one(LENS, decision).splitlines()
        assert lines[lines.index("- Detect: A setup method asserts.") + 1] == "- Not when: It is parametric."

    def test_new_rule_goes_at_the_end(self) -> None:
        block = "### LIFE-003: Match the reply\n- Severity: P0\n- Flag: Match the request id."
        text = apply_step.apply_one(
            LENS, _edit(action="new_rule", rule_id="LIFE-003", severity="P0", proposed_text=block)
        )
        assert text.endswith(block + "\n")

    def test_mismatches_are_refused(self) -> None:
        cases = [
            (_edit(current_text="A setup method raises."), "appears 0 times"),
            (_edit(rule_id="LIFE-009"), "appears 0 times in the lens file"),
            (_edit(field="Ref"), "unknown field"),
            (_edit(rule_id="LIFE-002", field="Not when", current_text=None), "already has a '- Not when:' line"),
            (_edit(action="new_rule", rule_id="LIFE-003", severity="P0", proposed_text="LIFE-003 text"), "must start"),
            (
                _edit(
                    action="new_rule",
                    rule_id="LIFE-003",
                    severity="P1",
                    proposed_text="### LIFE-003: x\n- Severity: P0\n- Flag: y",
                ),
                "Severity line",
            ),
            (
                _edit(
                    action="new_rule",
                    rule_id="LIFE-001",
                    severity="P0",
                    proposed_text="### LIFE-001: x\n- Severity: P0\n- Flag: y",
                ),
                "share an ID",
            ),
        ]
        for decision, message in cases:
            with pytest.raises(apply_step.ApplyError, match=message):
                apply_step.apply_one(LENS, decision)

    def test_exceptions_only_add_text(self) -> None:
        wrong_field = _edit(action="add_not_when", proposed_text="It is parametric.")
        with pytest.raises(apply_step.ApplyError, match="only change the Not when field"):
            apply_step.apply_one(LENS, wrong_field)
        current = "The delay is the behavior under test."
        replaced = _edit(action="add_not_when", rule_id="LIFE-002", field="Not when", current_text=current)
        with pytest.raises(apply_step.ApplyError, match="keep the current Not when text"):
            apply_step.apply_one(LENS, {**replaced, "proposed_text": "It is parametric."})
        text = apply_step.apply_one(LENS, {**replaced, "proposed_text": f"{current} It is parametric."})
        assert f"- Not when: {current} It is parametric.\n" in text

    def test_a_lone_carriage_return_is_refused(self) -> None:
        for separator in ("\r", "\r\n", "\u2028"):
            injected = _edit(proposed_text=f"x{separator}### LIFE-777: evil")
            with pytest.raises(apply_step.ApplyError, match="must be one line"):
                apply_step.apply_one(LENS, injected)

    def test_undo_names_only_the_edited_files(self) -> None:
        results = [
            {"lens": "lifecycle-and-isolation", "result": "applied"},
            {"lens": "lifecycle-and-isolation", "result": "applied"},
            {"lens": "test-effectiveness", "result": "skipped"},
        ]
        assert apply_step.edited_files(results) == [".agents/rules/code-review/lifecycle-and-isolation.md"]
        assert apply_step.edited_files([]) == []

    def test_a_value_must_be_one_line(self) -> None:
        injected = _edit(proposed_text="x\n### LIFE-777: evil\n- Severity: P0\n- Flag: z")
        with pytest.raises(apply_step.ApplyError, match="must be one line"):
            apply_step.apply_one(LENS, injected)

    def test_other_sections_and_bytes_stay_as_they_are(self) -> None:
        lens = LENS + "\n## Notes\n\nA note.\f\n\n"
        edited = apply_step.apply_one(lens, _edit(rule_id="LIFE-002", field="Flag", current_text="Do not sleep.",
                                                  proposed_text="Do not use a fixed sleep."))  # fmt: skip
        assert edited == lens.replace("- Flag: Do not sleep.", "- Flag: Do not use a fixed sleep.")
        block = "### LIFE-003: Match the reply\n- Severity: P0\n- Flag: Match the request id."
        added = apply_step.apply_one(
            lens, _edit(action="new_rule", rule_id="LIFE-003", severity="P0", proposed_text=block)
        )
        assert added.index("### LIFE-003") < added.index("## Notes")
        assert added.endswith("A note.\f\n\n")

    def _repo(self, tmp_path: Path) -> Path:
        _git(tmp_path, "init", "-q")
        lens = tmp_path / ".agents" / "rules" / "code-review" / "lifecycle-and-isolation.md"
        lens.parent.mkdir(parents=True)
        lens.write_text(LENS, encoding="utf-8")
        _git(tmp_path, "add", ".")
        _git(tmp_path, "commit", "-q", "-m", "Add lens (#1)")
        return lens

    def test_apply_run_edits_and_records(self, tmp_path: Path) -> None:
        lens = self._repo(tmp_path)
        run = tmp_path / "run"
        bad = _edit(rule_id="LIFE-009")
        skipped = {**bad, "status": "not_enough_evidence"}
        write_json(run / "decisions.json", [{**_edit(), "status": "apply"}, {**bad, "status": "apply"}, skipped])
        results = apply_step.apply_run(run, tmp_path)
        assert [r["result"] for r in results] == ["applied", "skipped"]
        assert "asserts or raises" in lens.read_text(encoding="utf-8")
        assert read_json(run / "applied.json") == results

    def test_lens_with_local_changes_is_not_touched(self, tmp_path: Path) -> None:
        lens = self._repo(tmp_path)
        lens.write_text(LENS + "\nlocal note\n", encoding="utf-8")
        run = tmp_path / "run"
        write_json(run / "decisions.json", [{**_edit(), "status": "apply"}])
        results = apply_step.apply_run(run, tmp_path)
        assert results[0]["reason"] == "the lens file has local changes"
        assert "asserts or raises" not in lens.read_text(encoding="utf-8")


class _FakeGitHub:
    def __init__(self, open_prs: list[Json]) -> None:
        self.open_prs = open_prs
        self.calls: list[tuple[str, str, object]] = []

    def request(self, method: str, path: str, data: dict[str, object] | None = None) -> object:
        self.calls.append((method, path, data))
        return self.open_prs if method == "GET" else {"html_url": "https://github.com/pr", "number": 1}


@features.not_reported
@scenarios.test_the_test
class Test_ReviewLearningOpenPr:
    def _repo_with_change(self, tmp_path: Path) -> tuple[Path, Path]:
        repo = tmp_path / "repo"
        repo.mkdir()
        lens = repo / ".agents" / "rules" / "code-review" / "lifecycle-and-isolation.md"
        lens.parent.mkdir(parents=True)
        lens.write_text(LENS, encoding="utf-8")
        _git(repo, "init", "-q")
        _git(repo, "config", "commit.gpgsign", "false")
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", "Add lens (#1)")
        lens.write_text(LENS.replace("Do not sleep.", "Do not use a fixed sleep."), encoding="utf-8")
        run = tmp_path / "run"
        write_json(run / "index.json", {"start": "2026-10-01", "end": "2026-10-31", "pull_requests": []})
        (run / "report.md").write_text("# Review learning\n", encoding="utf-8")
        return repo, run

    def test_only_lens_files_can_be_published(self) -> None:
        open_pr.check_paths([".agents/rules/code-review/test-effectiveness.md"])
        for path in ("utils/scripts/review_learning/x.py", ".agents/rules/code-review/sub/x.md", ".gitlab-ci.yml"):
            with pytest.raises(open_pr.UnexpectedChangeError):
                open_pr.check_paths([path])

    def test_body_holds_the_guide_and_a_cut_report(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _, run = self._repo_with_change(tmp_path)
        monkeypatch.setattr(open_pr, "MAX_REPORT_CHARS", 10)
        (run / "report.md").write_text("x" * 50, encoding="utf-8")
        body = open_pr.pr_body(run, "https://gitlab/job/1")
        assert body.startswith(open_pr.REVIEW_GUIDE)
        assert "Job: https://gitlab/job/1" in body
        assert "x" * 10 + "\n\n[The report is cut here." in body
        assert open_pr.pr_title(run) == "Review learning: rule changes from 2026-10-01 to 2026-10-31"

    def _publish(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, open_prs: list[Json]) -> _FakeGitHub:
        repo, run = self._repo_with_change(tmp_path)
        pushed: list[str] = []

        def fake_push(_root: Path, base_sha: str, _github: object, _env: object, branch: str) -> str:
            pushed.append(branch)
            return base_sha

        monkeypatch.setattr(open_pr, "push_signed_commit", fake_push)
        github = _FakeGitHub(open_prs)
        paths = open_pr.changed_paths(repo)
        assert paths == [".agents/rules/code-review/lifecycle-and-isolation.md"]
        open_pr.publish(repo, run, paths, github, {})  # type: ignore[arg-type]
        assert pushed == [open_pr.BRANCH]
        assert "Do not use a fixed sleep." in _git(
            repo, "show", "HEAD:.agents/rules/code-review/lifecycle-and-isolation.md"
        )
        return github

    def test_publish_opens_a_draft_pull_request(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        github = self._publish(tmp_path, monkeypatch, open_prs=[])
        method, path, data = github.calls[-1]
        assert (method, path) == ("POST", "/repos/DataDog/system-tests/pulls")
        assert isinstance(data, dict)
        assert data["draft"] is True
        assert data["head"] == open_pr.BRANCH
        assert all("merge" not in call[1] for call in github.calls)

    def test_an_open_pull_request_is_never_touched(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo, run = self._repo_with_change(tmp_path)

        def must_not_push(*_args: object) -> str:
            raise AssertionError("an open pull request must stop the push")

        monkeypatch.setattr(open_pr, "push_signed_commit", must_not_push)
        github = _FakeGitHub([{"number": 42}])
        result = open_pr.publish(repo, run, open_pr.changed_paths(repo), github, {})  # type: ignore[arg-type]
        assert result == "#42 is still open: review and close it first. Nothing is published."
        assert [call[0] for call in github.calls] == ["GET"]
        assert _git(repo, "branch", "--show-current") != open_pr.BRANCH

    def test_publish_keeps_the_local_git_identity(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._publish(tmp_path, monkeypatch, open_prs=[])
        config = subprocess.run(
            ["git", "config", "--local", "user.name"], cwd=tmp_path / "repo", capture_output=True, check=False
        )
        assert config.returncode != 0, "the commit identity must not be saved in the repository config"

    def test_mentions_in_the_report_never_notify(self, tmp_path: Path) -> None:
        _, run = self._repo_with_change(tmp_path)
        (run / "report.md").write_text("Ask @DataDog/some-team to merge", encoding="utf-8")
        body = open_pr.pr_body(run, None)
        assert "@DataDog/some-team" not in body
        assert "@\u200bDataDog/some-team" in body

    def test_publishing_outside_gitlab_is_refused(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo, run = self._repo_with_change(tmp_path)
        monkeypatch.delenv("GITLAB_CI", raising=False)
        monkeypatch.setattr("sys.argv", ["open_pr", "--run", str(run), "--repo-root", str(repo)])
        with pytest.raises(SystemExit, match="only publishes from the GitLab job"):
            open_pr.main()


BASE_LENS = "# Lifecycle\n\n### LIFE-001: Wait for data\n- Severity: P1\n- Flag: A flag.\n\n### LIFE-002: No sleep\n- Severity: P1\n- Flag: Old flag.\n"
HEAD_LENS = (
    "# Lifecycle\n\n### LIFE-001: Wait for data\n- Severity: P1\n- Flag: A flag.\n- Not when: It is parametric.\n\n"
    "### LIFE-002: No sleep\n- Severity: P1\n- Flag: New flag.\n\n### LIFE-003: New rule\n- Severity: P1\n- Flag: Match the id.\n"
)
LENS_PATH = ".agents/rules/code-review/lifecycle-and-isolation.md"


def _node(body: str, association: str = "MEMBER", login: str = "alice", kind: str = "User") -> Json:
    return {"id": f"c-{body}", "body": body, "url": "u", "authorAssociation": association,
            "author": {"login": login, "__typename": kind}}  # fmt: skip


def _review_thread(body: str, line: int | None = 10, *, resolved: bool = False) -> Json:
    return {"id": f"t-{body}", "isResolved": resolved, "path": LENS_PATH, "line": line, "startLine": None,
            "diffSide": "RIGHT", "startDiffSide": None, "comments": {"nodes": [_node(body)]}}  # fmt: skip


def _feedback_item(kind: str, body: str = "", line: int | None = None, **extra: object) -> Json:
    inline = line is not None
    return {"id": body or kind, "url": "u", "author": "alice", "kind": kind, "body": body,
            "thread_id": f"t-{body}" if inline else None, "path": LENS_PATH if inline else None, "line": line,
            "start_line": line, "side": "RIGHT" if inline else None, "diff_side": "RIGHT" if inline else None,
            "suggestion": None,
            "rule_ids": address.discard_ids(body) or [], **extra}  # fmt: skip


@features.not_reported
@scenarios.test_the_test
class Test_ReviewLearningAddress:
    @staticmethod
    def _repo(tmp_path: Path) -> tuple[Path, str]:
        repo = tmp_path / "repo"
        (repo / ".agents" / "rules" / "code-review").mkdir(parents=True)
        _git(repo, "init", "-q", "-b", "main")
        (repo / LENS_PATH).write_text(BASE_LENS, encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", "base")
        _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        (repo / LENS_PATH).write_text(HEAD_LENS, encoding="utf-8")
        _git(repo, "commit", "-q", "-am", "rule changes")
        return repo, _git(repo, "rev-parse", "HEAD")

    def test_kind_of_each_answer(self) -> None:
        assert address.kind_of("```suggestion\n- Flag: x\n```", inline=True) == "suggestion"
        assert address.kind_of("```suggestion\n- Flag: x\n```", inline=False) == "other"
        assert [address.kind_of(b, inline=True) for b in ["", "OK.", "LGTM", "👍"]] == ["approve"] * 4
        assert address.kind_of("Discard: it is too broad", inline=True) == "discard"
        assert address.kind_of("descarta: no aporta nada", inline=True) == "discard"
        assert address.kind_of("I would not discard it", inline=True) == "other"
        assert address.kind_of("Discard the second example", inline=True) == "other"
        assert address.kind_of("Remove the second example from Not when", inline=True) == "other"
        assert address.discard_ids("discard LIFE-003: LIFE-001 already covers it") == ["LIFE-003"]
        assert address.discard_ids("Discard - too broad") == []
        assert address.kind_of("discard-ish wording is fine", inline=True) == "other"
        assert address.kind_of("Discard\n\nIt repeats TEST-002", inline=True) == "discard"

    def test_only_open_threads_of_reviewers_count(self) -> None:
        pull_request = {
            "comments": {"nodes": [_node("LGTM"), _node("ok", association="CONTRIBUTOR"), _node("ok", kind="Bot")]},
            "reviews": {"nodes": [_node(""), _node("Discard LIFE-003")]},
            "reviewThreads": {"nodes": [_review_thread("Discard"), _review_thread("old", resolved=True)]},
        }
        items = address.items_of(pull_request)
        assert [(i["body"], i["kind"]) for i in items] == [("LGTM", "approve"), ("Discard LIFE-003", "discard"),
                                                            ("Discard", "discard")]  # fmt: skip
        assert items[1]["rule_ids"] == ["LIFE-003"]
        assert items[2]["thread_id"] == "t-Discard"
        assert items[2]["line"] == 10

    def test_fetch_refuses_another_branch(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        page = {"pageInfo": {"hasNextPage": False}, "nodes": []}
        pull_request = {"headRefName": "feature", "headRefOid": "abc", "comments": page, "reviews": page,
                        "reviewThreads": {"pageInfo": {"hasNextPage": True}, "nodes": []}}  # fmt: skip

        def graphql(_query: str, _variables: dict[str, str]) -> Json:
            return {"data": {"repository": {"pullRequest": pull_request}}}

        with pytest.raises(SystemExit, match="not a review-learning pull request"):
            address.fetch(1, graphql)
        pull_request["headRefName"] = address.BRANCH
        with pytest.raises(SystemExit, match="more than 100"):
            address.fetch(1, graphql)

    def test_apply_suggestion_and_discards(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo, head = self._repo(tmp_path)
        monkeypatch.chdir(repo)
        items = [
            _feedback_item("suggestion", "suggest", line=10, suggestion="- Flag: Reviewer flag.\n"),
            _feedback_item("discard", "Discard", line=13),
            _feedback_item("discard", "Discard LIFE-001: it is too broad"),
            _feedback_item("approve", "ok"),
            _feedback_item("other", "Say why", line=5),
        ]
        write_json(address.run_dir(1) / "feedback.json", {"pr": 1, "head": head, "items": items})
        result = address.apply_pr(1, repo)
        statuses = [i["status"] for i in result["items"]]
        assert statuses == ["applied", "applied", "applied", "kept", "for the skill"]
        expected = BASE_LENS.replace("Old flag.", "Reviewer flag.")
        assert (repo / LENS_PATH).read_text(encoding="utf-8") == expected

    def test_unsafe_comments_are_skipped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo, head = self._repo(tmp_path)
        monkeypatch.chdir(repo)
        items = [
            _feedback_item("suggestion", "suggest", line=10, suggestion="- Flag: Reviewer flag.\n"),
            _feedback_item("discard", "Discard: the rule is wrong", line=9),
            _feedback_item("discard", "Discard", line=None, path=LENS_PATH, thread_id="t-x"),
            _feedback_item("suggestion", "left", line=5, side="LEFT", suggestion="x\n"),
            _feedback_item("discard", "discard LIFE-003"),
            _feedback_item("discard", "discard LIFE-003."),
        ]
        write_json(address.run_dir(1) / "feedback.json", {"pr": 1, "head": head, "items": items})
        statuses = [i["status"] for i in address.apply_pr(1, repo)["items"]]
        assert statuses == [
            "skipped: a discard of the same rule wins",
            "applied",
            "skipped: the comment has no line: name the rule ID, such as 'discard LIFE-003'",
            "skipped: the suggestion is not on the current lines of the file",
            "applied",
            "applied",
        ]
        expected = HEAD_LENS.split("\n\n### LIFE-003")[0].replace("New flag.", "Old flag.") + "\n"
        assert (repo / LENS_PATH).read_text(encoding="utf-8") == expected

    def test_discard_on_a_removed_line(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo, head = self._repo(tmp_path)
        monkeypatch.chdir(repo)
        # Line 7 is the heading of LIFE-002 in the merge base, but a line of LIFE-001 in the head.
        items = [_feedback_item("discard", "Discard", line=7, side="LEFT", diff_side="LEFT")]
        write_json(address.run_dir(1) / "feedback.json", {"pr": 1, "head": head, "items": items})
        assert [i["status"] for i in address.apply_pr(1, repo)["items"]] == ["applied"]
        assert "- Flag: Old flag." in (repo / LENS_PATH).read_text(encoding="utf-8")
        assert "- Not when: It is parametric." in (repo / LENS_PATH).read_text(encoding="utf-8")

    def test_overlapping_suggestions_apply_once(self) -> None:
        lines = ["a", "b", "c"]
        items = [
            {"id": "one", "line": 2, "start_line": 1, "suggestion": "x\n"},
            {"id": "two", "line": 2, "start_line": 2, "suggestion": "y\n"},
        ]
        status = address.apply_suggestions(lines, items)
        assert status == {"one": "applied", "two": "skipped: it overlaps another suggestion"}
        assert lines == ["x", "c"]

    def test_apply_needs_a_clean_checkout_of_the_head(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo, head = self._repo(tmp_path)
        monkeypatch.chdir(repo)
        write_json(address.run_dir(1) / "feedback.json", {"pr": 1, "head": "0" * 40, "items": []})
        with pytest.raises(SystemExit, match="check out the pull request head"):
            address.apply_pr(1, repo)
        write_json(address.run_dir(1) / "feedback.json", {"pr": 1, "head": head, "items": []})
        (repo / LENS_PATH).write_text("changed\n", encoding="utf-8")
        with pytest.raises(SystemExit, match="local changes"):
            address.apply_pr(1, repo)

    def test_resolve_only_handled_threads(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        applied = [
            {**_feedback_item("discard", "a", line=3), "status": "applied"},
            {**_feedback_item("other", "b", line=4), "status": "for the skill"},
            {**_feedback_item("other", "c", line=5), "status": "for the skill"},
            {**_feedback_item("approve", "ok"), "status": "kept"},
        ]
        write_json(address.run_dir(1) / "applied.json", applied)
        calls: list[str] = []

        def graphql(_query: str, variables: dict[str, str]) -> Json:
            calls.append(variables["id"])
            return {}

        assert address.resolve(1, ["b"], graphql) == ["t-a", "t-b"]
        assert calls == ["t-a", "t-b"]
