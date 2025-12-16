from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from pygtrie import StringTrie

from utils import scenarios, features
from utils.scripts.activate_easy_wins.const import LIBRARIES
from utils.scripts.activate_easy_wins.core import tup_to_rule, tups_to_rule
from utils.scripts.activate_easy_wins.test_artifact import (
    ActivationStatus,
    TestData as TestDataClass,  # Rename to avoid pytest collection warning
    parse_artifact_data,
)
from utils.scripts.activate_easy_wins.types import Context


@scenarios.test_the_test
@features.not_reported
class Test_Tup_To_Rule:
    def test_single_element(self):
        """Test converting a single-element tuple to a rule"""
        result = tup_to_rule(("tests/test_file.py",))
        assert result == "tests/test_file.py"

    def test_file_path(self):
        """Test converting a file path tuple to a rule"""
        result = tup_to_rule(("tests", "test_file.py"))
        assert result == "tests/test_file.py"

    def test_class_path(self):
        """Test converting a class path tuple to a rule"""
        result = tup_to_rule(("tests", "test_file.py", "Test_Class"))
        assert result == "tests/test_file.py::Test_Class"

    def test_method_path(self):
        """Test converting a method path tuple to a rule"""
        result = tup_to_rule(("tests", "test_file.py", "Test_Class", "test_method"))
        assert result == "tests/test_file.py::Test_Class::test_method"

    def test_nested_path(self):
        """Test converting a nested path tuple to a rule"""
        result = tup_to_rule(("tests", "subdir", "test_file.py", "Test_Class", "test_method"))
        assert result == "tests/subdir/test_file.py::Test_Class::test_method"

    def test_separator_change_on_py_file(self):
        """Test that separator changes from / to :: after .py file"""
        result = tup_to_rule(("tests", "dir", "test.py", "Test_Class", "test_method"))
        assert result == "tests/dir/test.py::Test_Class::test_method"
        assert "::" in result
        assert result.count("::") == 2  # One after .py, one before method


@scenarios.test_the_test
@features.not_reported
class Test_Tups_To_Rule:
    def test_empty_list(self):
        """Test converting an empty list of tuples"""
        result = tups_to_rule([])
        assert result == []

    def test_single_tuple(self):
        """Test converting a single tuple"""
        # Type annotation is restrictive but function accepts varying lengths
        input_tuples: list[tuple[str, ...]] = [("tests", "test_file.py")]
        result = tups_to_rule(input_tuples)  # type: ignore[arg-type]
        assert result == ["tests/test_file.py"]

    def test_multiple_tuples(self):
        """Test converting multiple tuples"""
        # Type annotation is restrictive but function accepts varying lengths
        input_tuples: list[tuple[str, ...]] = [
            ("tests", "test_file.py"),
            ("tests", "test_file.py", "Test_Class"),
            ("tests", "test_file.py", "Test_Class", "test_method"),
        ]
        result = tups_to_rule(input_tuples)  # type: ignore[arg-type]
        assert result == [
            "tests/test_file.py",
            "tests/test_file.py::Test_Class",
            "tests/test_file.py::Test_Class::test_method",
        ]

    def test_preserves_order(self):
        """Test that order is preserved"""
        # Type annotation is restrictive but function accepts varying lengths
        input_tuples: list[tuple[str, ...]] = [
            ("tests", "b.py"),
            ("tests", "a.py"),
            ("tests", "c.py"),
        ]
        result = tups_to_rule(input_tuples)  # type: ignore[arg-type]
        assert result == ["tests/b.py", "tests/a.py", "tests/c.py"]


@scenarios.test_the_test
@features.not_reported
class Test_Context_Create:
    def test_valid_context_creation(self):
        """Test creating a valid Context object"""
        context = Context.create("python", "1.2.3", "flask")
        assert context is not None
        assert context.library == "python"
        assert str(context.library_version) == "1.2.3"
        assert context.variant == "flask"

    def test_invalid_library(self):
        """Test that invalid library returns None"""
        context = Context.create("invalid_lib", "1.2.3", "flask")
        assert context is None

    def test_empty_version(self):
        """Test that empty version returns None"""
        context = Context.create("python", "", "flask")
        assert context is None

    def test_none_version(self):
        """Test that None version returns None"""
        context = Context.create("python", None, "flask")  # type: ignore[arg-type]
        assert context is None

    def test_invalid_version_format(self):
        """Test that invalid version format raises ValueError"""
        # Version() raises ValueError for invalid formats
        # The walrus operator will fail, causing the function to return None
        # But if Version() raises, the exception propagates
        # Based on actual behavior, Version raises ValueError
        with pytest.raises(ValueError, match="Version string lacks a numerical component"):
            Context.create("python", "invalid_version", "flask")

    def test_all_valid_libraries(self):
        """Test that all valid libraries from const can be created"""
        for library in LIBRARIES:
            context = Context.create(library, "1.0.0", "test_variant")
            assert context is not None, f"Failed to create context for {library}"
            assert context.library == library

    def test_context_hashable(self):
        """Test that Context objects are hashable"""
        context1 = Context.create("python", "1.2.3", "flask")
        context2 = Context.create("python", "1.2.3", "flask")
        context3 = Context.create("python", "1.2.4", "flask")

        assert context1 is not None
        assert context2 is not None
        assert context3 is not None

        assert hash(context1) == hash(context2)
        assert hash(context1) != hash(context3)


@scenarios.test_the_test
@features.not_reported
class Test_Parse_Artifact_Data:
    def test_empty_directory(self):
        """Test parsing an empty directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            test_data, weblogs = parse_artifact_data(data_dir, ["python"])
            assert test_data == {}
            assert weblogs == {}

    def test_skip_dev_and_parametric(self):
        """Test that _dev_ and _parametric_ directories are skipped"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            # Create directories that should be skipped
            (data_dir / "some_dev_directory").mkdir()
            (data_dir / "some_parametric_directory").mkdir()
            (data_dir / "normal_directory").mkdir()

            test_data, weblogs = parse_artifact_data(data_dir, ["python"])
            assert test_data == {}
            assert weblogs == {}

    def test_missing_report_json(self):
        """Test handling missing report.json files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            scenario_dir = data_dir / "normal_directory" / "scenario1"
            scenario_dir.mkdir(parents=True)

            test_data, weblogs = parse_artifact_data(data_dir, ["python"])
            assert test_data == {}
            assert weblogs == {}

    def test_single_xpassed_test(self):
        """Test parsing a single xpassed test"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            scenario_dir = data_dir / "normal_directory" / "scenario1"
            scenario_dir.mkdir(parents=True)

            report_data = {
                "context": {
                    "library_name": "python",
                    "library": "1.2.3",  # library field is the version string
                    "weblog_variant": "flask",
                },
                "tests": [
                    {
                        "nodeid": "tests/test_file.py::Test_Class::test_method",
                        "outcome": "xpassed",
                    }
                ],
            }

            with scenario_dir.joinpath("report.json").open("w", encoding="utf-8") as f:
                json.dump(report_data, f)

            test_data, weblogs = parse_artifact_data(data_dir, ["python"])

            assert len(test_data) == 1
            context = list(test_data.keys())[0]
            assert context.library == "python"
            assert context.variant == "flask"
            assert "tests/test_file.py::Test_Class::test_method" in test_data[context].xpass_nodes
            assert weblogs["python"] == {"flask"}

    def test_xfailed_test(self):
        """Test parsing an xfailed test"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            scenario_dir = data_dir / "normal_directory" / "scenario1"
            scenario_dir.mkdir(parents=True)

            report_data = {
                "context": {
                    "library_name": "python",
                    "library": "1.2.3",  # library field is the version string
                    "weblog_variant": "flask",
                },
                "tests": [
                    {
                        "nodeid": "tests/test_file.py::Test_Class::test_method",
                        "outcome": "xfailed",
                    }
                ],
            }

            with scenario_dir.joinpath("report.json").open("w", encoding="utf-8") as f:
                json.dump(report_data, f)

            test_data, weblogs = parse_artifact_data(data_dir, ["python"])

            assert len(test_data) == 1
            assert "python" in weblogs
            context = list(test_data.keys())[0]
            # Check that the trie contains XFAIL status
            # The nodeid is converted from :: to / in the parsing logic
            nodeid_slice = "tests/test_file.py/Test_Class/test_method"
            status = test_data[context].trie.get(nodeid_slice)
            assert status == ActivationStatus.XFAIL

    def test_passed_test(self):
        """Test parsing a passed test"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            scenario_dir = data_dir / "normal_directory" / "scenario1"
            scenario_dir.mkdir(parents=True)

            report_data = {
                "context": {
                    "library_name": "python",
                    "library": "1.2.3",  # library field is the version string
                    "weblog_variant": "flask",
                },
                "tests": [
                    {
                        "nodeid": "tests/test_file.py::Test_Class::test_method",
                        "outcome": "passed",
                    }
                ],
            }

            with scenario_dir.joinpath("report.json").open("w", encoding="utf-8") as f:
                json.dump(report_data, f)

            test_data, weblogs = parse_artifact_data(data_dir, ["python"])

            assert len(test_data) == 1
            assert "python" in weblogs
            context = list(test_data.keys())[0]
            # The nodeid is converted from :: to / in the parsing logic
            nodeid_slice = "tests/test_file.py/Test_Class/test_method"
            status = test_data[context].trie.get(nodeid_slice)
            assert status == ActivationStatus.PASS

    def test_multiple_tests_same_context(self):
        """Test parsing multiple tests in the same context"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            scenario_dir = data_dir / "normal_directory" / "scenario1"
            scenario_dir.mkdir(parents=True)

            report_data = {
                "context": {
                    "library_name": "python",
                    "library": "1.2.3",  # library field is the version string
                    "weblog_variant": "flask",
                },
                "tests": [
                    {
                        "nodeid": "tests/test_file.py::Test_Class::test_method1",
                        "outcome": "xpassed",
                    },
                    {
                        "nodeid": "tests/test_file.py::Test_Class::test_method2",
                        "outcome": "xpassed",
                    },
                ],
            }

            with scenario_dir.joinpath("report.json").open("w", encoding="utf-8") as f:
                json.dump(report_data, f)

            test_data, weblogs = parse_artifact_data(data_dir, ["python"])

            assert len(test_data) == 1
            assert "python" in weblogs
            context = list(test_data.keys())[0]
            assert len(test_data[context].xpass_nodes) == 2

    def test_multiple_contexts(self):
        """Test parsing multiple contexts"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)

            # First context
            scenario_dir1 = data_dir / "normal_directory" / "scenario1"
            scenario_dir1.mkdir(parents=True)
            report_data1 = {
                "context": {
                    "library_name": "python",
                    "library": "1.2.3",  # library field is the version string
                    "weblog_variant": "flask",
                },
                "tests": [{"nodeid": "tests/test1.py::Test1::test1", "outcome": "xpassed"}],
            }
            with scenario_dir1.joinpath("report.json").open("w", encoding="utf-8") as f:
                json.dump(report_data1, f)

            # Second context
            scenario_dir2 = data_dir / "normal_directory" / "scenario2"
            scenario_dir2.mkdir(parents=True)
            report_data2 = {
                "context": {
                    "library_name": "java",
                    "library": "1.8.0",  # library field is the version string
                    "weblog_variant": "spring",
                },
                "tests": [{"nodeid": "tests/test2.py::Test2::test2", "outcome": "xpassed"}],
            }
            with scenario_dir2.joinpath("report.json").open("w", encoding="utf-8") as f:
                json.dump(report_data2, f)

            test_data, weblogs = parse_artifact_data(data_dir, ["python", "java"])

            assert len(test_data) == 2
            assert "python" in weblogs
            assert "java" in weblogs
            assert weblogs["python"] == {"flask"}
            assert weblogs["java"] == {"spring"}

    def test_filter_by_libraries(self):
        """Test that only specified libraries are parsed"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            scenario_dir = data_dir / "normal_directory" / "scenario1"
            scenario_dir.mkdir(parents=True)

            report_data = {
                "context": {
                    "library_name": "python",
                    "library": "1.2.3",  # library field is the version string
                    "weblog_variant": "flask",
                },
                "tests": [{"nodeid": "tests/test.py::Test::test", "outcome": "xpassed"}],
            }

            with scenario_dir.joinpath("report.json").open("w", encoding="utf-8") as f:
                json.dump(report_data, f)

            # Request only java, should filter out python
            test_data, weblogs = parse_artifact_data(data_dir, ["java"])
            assert test_data == {}
            assert weblogs == {}

    def test_trie_status_conflicts(self):
        """Test that trie status conflicts are handled correctly"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            scenario_dir = data_dir / "normal_directory" / "scenario1"
            scenario_dir.mkdir(parents=True)

            # XFAIL followed by XPASS should result in NONE
            report_data = {
                "context": {
                    "library_name": "python",
                    "library": "1.2.3",  # library field is the version string
                    "weblog_variant": "flask",
                },
                "tests": [
                    {
                        "nodeid": "tests/test_file.py::Test_Class::test_method",
                        "outcome": "xfailed",
                    },
                    {
                        "nodeid": "tests/test_file.py::Test_Class::test_method",
                        "outcome": "xpassed",
                    },
                ],
            }

            with scenario_dir.joinpath("report.json").open("w", encoding="utf-8") as f:
                json.dump(report_data, f)

            test_data, _ = parse_artifact_data(data_dir, ["python"])

            assert len(test_data) == 1
            context = list(test_data.keys())[0]
            # The nodeid is converted from :: to / in the parsing logic
            nodeid_slice = "tests/test_file.py/Test_Class/test_method"
            status = test_data[context].trie.get(nodeid_slice)
            # XFAIL + XPASS should result in NONE
            assert status == ActivationStatus.NONE

    def test_trie_path_slices(self):
        """Test that trie contains all path slices"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            scenario_dir = data_dir / "normal_directory" / "scenario1"
            scenario_dir.mkdir(parents=True)

            report_data = {
                "context": {
                    "library_name": "python",
                    "library": "1.2.3",  # library field is the version string
                    "weblog_variant": "flask",
                },
                "tests": [
                    {
                        "nodeid": "tests/test_file.py::Test_Class::test_method",
                        "outcome": "xpassed",
                    }
                ],
            }

            with scenario_dir.joinpath("report.json").open("w", encoding="utf-8") as f:
                json.dump(report_data, f)

            test_data, _ = parse_artifact_data(data_dir, ["python"])

            assert len(test_data) == 1
            context = list(test_data.keys())[0]
            trie = test_data[context].trie

            # Check that all path slices are in the trie
            # The nodeid is converted from :: to / in the parsing logic
            assert trie.get("tests") is not None
            assert trie.get("tests/test_file.py") is not None
            assert trie.get("tests/test_file.py/Test_Class") is not None
            assert trie.get("tests/test_file.py/Test_Class/test_method") is not None

    def test_invalid_context_skipped(self):
        """Test that invalid contexts are skipped"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            scenario_dir = data_dir / "normal_directory" / "scenario1"
            scenario_dir.mkdir(parents=True)

            # Invalid library name
            report_data = {
                "context": {
                    "library_name": "invalid_lib",
                    "library": "invalid_lib",
                    "weblog_variant": "flask",
                },
                "tests": [{"nodeid": "tests/test.py::Test::test", "outcome": "xpassed"}],
            }

            with scenario_dir.joinpath("report.json").open("w", encoding="utf-8") as f:
                json.dump(report_data, f)

            test_data, weblogs = parse_artifact_data(data_dir, ["python"])
            assert test_data == {}
            assert weblogs == {}

    def test_context_not_in_libraries_list(self):
        """Test that contexts with libraries not in the libraries list are skipped"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            scenario_dir = data_dir / "normal_directory" / "scenario1"
            scenario_dir.mkdir(parents=True)

            # Valid library but not in the requested list
            report_data = {
                "context": {
                    "library_name": "java",
                    "library": "1.8.0",  # library field is the version string
                    "weblog_variant": "spring",
                },
                "tests": [{"nodeid": "tests/test.py::Test::test", "outcome": "xpassed"}],
            }

            with scenario_dir.joinpath("report.json").open("w", encoding="utf-8") as f:
                json.dump(report_data, f)

            # Request only python, should skip java
            test_data, weblogs = parse_artifact_data(data_dir, ["python"])
            assert test_data == {}
            assert weblogs == {}

    def test_weblog_collection(self):
        """Test that weblogs are collected correctly"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)

            # Multiple scenarios with different weblogs
            for i, weblog in enumerate(["flask", "django", "fastapi"]):
                scenario_dir = data_dir / "normal_directory" / f"scenario{i}"
                scenario_dir.mkdir(parents=True)
                report_data = {
                    "context": {
                        "library_name": "python",
                        "library": "1.2.3",  # library field is the version string
                        "weblog_variant": weblog,
                    },
                    "tests": [{"nodeid": "tests/test.py::Test::test", "outcome": "xpassed"}],
                }
                with scenario_dir.joinpath("report.json").open("w", encoding="utf-8") as f:
                    json.dump(report_data, f)

            test_data, weblogs = parse_artifact_data(data_dir, ["python"])

            # Verify test_data contains all contexts
            assert len(test_data) == 3  # One for each weblog variant
            assert "python" in weblogs
            assert weblogs["python"] == {"flask", "django", "fastapi"}


@scenarios.test_the_test
@features.not_reported
class Test_TestData_Structure:
    def test_test_data_iteration(self):
        """Test that TestData can be unpacked via iteration"""
        test_data = TestDataClass()
        test_data.xpass_nodes = ["node1", "node2"]
        test_data.trie["path1"] = ActivationStatus.XPASS

        nodes, trie = test_data
        assert nodes == ["node1", "node2"]
        assert isinstance(trie, StringTrie)

    def test_empty_test_data(self):
        """Test empty TestData"""
        test_data = TestDataClass()
        assert test_data.xpass_nodes == []
        assert len(test_data.trie) == 0
