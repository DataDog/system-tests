from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

import pytest
from pytest_split.algorithms import least_duration

from bazel.parametric.configuration import language_configuration
from bazel.parametric.sharding import (
    file_hash,
    load_duration_manifest,
    membership_hash,
    pytest_split_arguments,
    round_robin_indices,
)
from bazel.parametric.update_durations import aggregate_reports, find_reports


class Test_Sharding(unittest.TestCase):
    def test_aggregate_reports_uses_median_lifecycle_duration_and_sorts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports = [
                {
                    "tests": [
                        {
                            "nodeid": "test_b",
                            "setup": {"duration": 1.0},
                            "call": {"duration": 2.0},
                            "teardown": {"duration": 3.0},
                        },
                        {"nodeid": "test_a", "call": {"duration": 1.23456789}},
                    ]
                },
                {
                    "tests": [
                        {"nodeid": "test_a", "call": {"duration": 2.0}},
                        {"nodeid": "test_b", "call": {"duration": 2.0}},
                    ]
                },
                {"tests": [{"nodeid": "test_b", "call": {"duration": 4.0}}]},
            ]
            report_paths = []
            for index, report in enumerate(reports):
                report_path = root / f"report-{index}.json"
                report_path.write_text(json.dumps(report), encoding="utf-8")
                report_paths.append(report_path)

            assert aggregate_reports(report_paths) == {"test_a": 1.617284, "test_b": 4.0}

    def test_stable_tie_breaking_and_complete_shard_coverage(self) -> None:
        items = [SimpleNamespace(nodeid=node_id) for node_id in ("test_c", "test_a", "test_b", "test_d")]
        durations = {item.nodeid: 1.0 for item in items}

        first = least_duration(3, items, durations)
        second = least_duration(3, list(reversed(items)), durations)
        first_members = [{item.nodeid for item in group.selected} for group in first]
        second_members = [{item.nodeid for item in group.selected} for group in second]

        assert first_members == second_members
        assert set().union(*first_members) == set(durations)
        assert sum(len(group) for group in first_members) == len(durations)

    def test_manifest_and_membership_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "durations.json"
            content = '{"test_b": 2.0, "test_a": 1.0}\n'
            path.write_text(content, encoding="utf-8")

            assert load_duration_manifest(path) == {"test_a": 1.0, "test_b": 2.0}
            assert file_hash(path) == hashlib.sha256(content.encode()).hexdigest()
            expected_membership = hashlib.sha256(b"test_a\ntest_b\n").hexdigest()
            assert membership_hash(["test_b", "test_a"]) == expected_membership
            assert membership_hash(["test_a", "test_b"]) == expected_membership

    def test_duration_manifest_must_exist_and_not_be_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "durations.json"
            with pytest.raises(FileNotFoundError):
                load_duration_manifest(path)

            path.write_text("{}\n", encoding="utf-8")
            with pytest.raises(ValueError, match="non-empty"):
                load_duration_manifest(path)

    def test_find_reports_prefers_go_target_below_bazel_testlogs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unrelated_report = root / "other" / "report.json"
            go_report = root / "bazel" / "parametric" / "go" / "shard_1" / "report.json"
            unrelated_report.parent.mkdir(parents=True)
            go_report.parent.mkdir(parents=True)
            unrelated_report.write_text("{}", encoding="utf-8")
            go_report.write_text("{}", encoding="utf-8")

            assert find_reports(root) == [go_report]

    def test_find_reports_requires_target_and_isolates_mixed_testlogs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            go_report = root / "bazel" / "parametric" / "go" / "shard_1" / "report.json"
            python_report = root / "bazel" / "parametric" / "python" / "shard_1" / "report.json"
            go_report.parent.mkdir(parents=True)
            python_report.parent.mkdir(parents=True)
            go_report.write_text("{}", encoding="utf-8")
            python_report.write_text("{}", encoding="utf-8")

            with pytest.raises(ValueError, match="--target is required"):
                find_reports(root)
            assert find_reports(root, target="go") == [go_report]
            assert find_reports(root, target="python") == [python_report]

    def test_language_configurations_are_explicit_and_isolated(self) -> None:
        go = language_configuration("golang")
        python = language_configuration("python")

        assert go.artifact_environment_variable == "SYSTEM_TESTS_GO_PARAMETRIC_SERVER"
        assert go.duration_manifest == "go_test_durations.json"
        assert python.artifact_environment_variable == "SYSTEM_TESTS_PYTHON_PARAMETRIC_ARCHIVE"
        assert python.duration_manifest == "python_test_durations.json"
        with pytest.raises(ValueError, match="Unknown Bazel parametric language"):
            language_configuration("ruby")

    def test_pytest_split_arguments_include_duration_manifest(self) -> None:
        path = Path("go_test_durations.json")
        assert pytest_split_arguments(2, 1, path) == [
            "--splitting-algorithm=least_duration",
            "--durations-path=go_test_durations.json",
            "--splits=2",
            "--group=2",
        ]

    def test_round_robin_is_stable_and_covers_every_item_once(self) -> None:
        selections = [round_robin_indices(11, 3, shard)[0] for shard in range(3)]

        assert selections == [[0, 3, 6, 9], [1, 4, 7, 10], [2, 5, 8]]
        assert sorted(index for selection in selections for index in selection) == list(range(11))


if __name__ == "__main__":
    unittest.main()
