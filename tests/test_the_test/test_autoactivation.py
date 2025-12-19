from __future__ import annotations

import json
import tempfile
import textwrap
from pathlib import Path

import pytest
from pygtrie import StringTrie

from unittest.mock import Mock, patch

from utils import scenarios, features
from utils._context.component_version import Version
from utils.manifest import Condition, TestDeclaration
from utils.manifest._internal.types import SemverRange, SkipDeclaration
from utils.scripts.activate_easy_wins.const import LIBRARIES
from utils.scripts.activate_easy_wins.core import tup_to_rule, tups_to_rule, update_manifest
from utils.scripts.activate_easy_wins.manifest_editor import ManifestEditor
from utils.scripts.activate_easy_wins.test_artifact import (
    ActivationStatus,
    TestData as TestDataClass,  # Rename to avoid pytest collection warning
    parse_artifact_data,
    pull_artifact,
)
from utils.scripts.activate_easy_wins.types import Context


@scenarios.test_the_test
@features.not_reported
class Test_Tup_To_Rule:
    def test_separator_change_on_py_file(self):
        """Test that separator changes from / to :: after .py file"""
        result = tup_to_rule(("tests", "dir", "test.py", "Test_Class", "test_method"))
        assert result == "tests/dir/test.py::Test_Class::test_method"
        assert "::" in result
        assert result.count("::") == 2  # One after .py, one before method


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

            # Create dev directory with report.json that should be skipped
            dev_scenario_dir = data_dir / "some_dev_directory" / "scenario1"
            dev_scenario_dir.mkdir(parents=True)
            dev_report_data = {
                "context": {
                    "library_name": "python",
                    "library": "1.2.3",
                    "weblog_variant": "flask",
                },
                "tests": [{"nodeid": "tests/test.py::Test::test", "outcome": "xpassed"}],
            }
            with dev_scenario_dir.joinpath("report.json").open("w", encoding="utf-8") as f:
                json.dump(dev_report_data, f)

            # Create parametric directory with report.json that should be skipped
            parametric_scenario_dir = data_dir / "some_parametric_directory" / "scenario1"
            parametric_scenario_dir.mkdir(parents=True)
            parametric_report_data = {
                "context": {
                    "library_name": "python",
                    "library": "1.2.3",
                    "weblog_variant": "django",
                },
                "tests": [{"nodeid": "tests/test.py::Test::test", "outcome": "xpassed"}],
            }
            with parametric_scenario_dir.joinpath("report.json").open("w", encoding="utf-8") as f:
                json.dump(parametric_report_data, f)

            # Create normal directory with report.json that should be parsed
            normal_scenario_dir = data_dir / "normal_directory" / "scenario1"
            normal_scenario_dir.mkdir(parents=True)
            normal_report_data = {
                "context": {
                    "library_name": "python",
                    "library": "1.2.3",
                    "weblog_variant": "fastapi",
                },
                "tests": [{"nodeid": "tests/test.py::Test::test", "outcome": "xpassed"}],
            }
            with normal_scenario_dir.joinpath("report.json").open("w", encoding="utf-8") as f:
                json.dump(normal_report_data, f)

            test_data, weblogs = parse_artifact_data(data_dir, ["python"])

            # Verify that only the normal directory was parsed (dev and parametric were skipped)
            assert len(test_data) == 1
            context = list(test_data.keys())[0]
            assert context.library == "python"
            assert context.variant == "fastapi"  # Only the normal directory's weblog variant
            assert "python" in weblogs
            assert weblogs["python"] == {"fastapi"}  # Only fastapi, not flask or django

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

            # Check that the trie contains all path slices with correct status
            trie = test_data[context].trie
            # The nodeid is converted from :: to / in the parsing logic
            assert trie.get("tests") == ActivationStatus.XPASS
            assert trie.get("tests/test_file.py") == ActivationStatus.XPASS
            assert trie.get("tests/test_file.py/Test_Class") == ActivationStatus.XPASS
            nodeid_slice = "tests/test_file.py/Test_Class/test_method"
            assert trie.get(nodeid_slice) == ActivationStatus.XPASS

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
            # Check that the trie contains all path slices with XFAIL status
            trie = test_data[context].trie
            # The nodeid is converted from :: to / in the parsing logic
            assert trie.get("tests") == ActivationStatus.XFAIL
            assert trie.get("tests/test_file.py") == ActivationStatus.XFAIL
            assert trie.get("tests/test_file.py/Test_Class") == ActivationStatus.XFAIL
            nodeid_slice = "tests/test_file.py/Test_Class/test_method"
            assert trie.get(nodeid_slice) == ActivationStatus.XFAIL

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
            # Check that the trie contains all path slices with PASS status
            trie = test_data[context].trie
            # The nodeid is converted from :: to / in the parsing logic
            assert trie.get("tests") == ActivationStatus.PASS
            assert trie.get("tests/test_file.py") == ActivationStatus.PASS
            assert trie.get("tests/test_file.py/Test_Class") == ActivationStatus.PASS
            nodeid_slice = "tests/test_file.py/Test_Class/test_method"
            assert trie.get(nodeid_slice) == ActivationStatus.PASS

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
        """Test that trie status conflicts are handled correctly at higher levels"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            scenario_dir = data_dir / "normal_directory" / "scenario1"
            scenario_dir.mkdir(parents=True)

            # Different test methods with conflicting statuses should create conflicts at class/file level
            report_data = {
                "context": {
                    "library_name": "python",
                    "library": "1.2.3",  # library field is the version string
                    "weblog_variant": "flask",
                },
                "tests": [
                    {
                        "nodeid": "tests/test_file.py::Test_Class::test_method1",
                        "outcome": "xfailed",
                    },
                    {
                        "nodeid": "tests/test_file.py::Test_Class::test_method2",
                        "outcome": "xpassed",
                    },
                ],
            }

            with scenario_dir.joinpath("report.json").open("w", encoding="utf-8") as f:
                json.dump(report_data, f)

            test_data, _ = parse_artifact_data(data_dir, ["python"])

            assert len(test_data) == 1
            context = list(test_data.keys())[0]
            trie = test_data[context].trie
            # The nodeid is converted from :: to / in the parsing logic
            # Individual test methods should have their specific statuses
            assert trie.get("tests/test_file.py/Test_Class/test_method1") == ActivationStatus.XFAIL
            assert trie.get("tests/test_file.py/Test_Class/test_method2") == ActivationStatus.XPASS
            # The class level should have NONE due to conflicting child statuses
            assert trie.get("tests/test_file.py/Test_Class") == ActivationStatus.NONE
            # The file level should also have NONE due to conflicting child statuses
            assert trie.get("tests/test_file.py") == ActivationStatus.NONE
            # The tests directory level should also have NONE
            assert trie.get("tests") == ActivationStatus.NONE

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
class Test_ManifestEditor:
    def setup_manifest_editor(self, tmp_path: Path):
        """Create a temporary manifest file for testing"""
        manifest_dir = tmp_path / "manifests"
        manifest_dir.mkdir()

        # Create minimal manifest files for all libraries
        libraries = [
            "cpp_httpd",
            "cpp",
            "dotnet",
            "golang",
            "java",
            "nodejs",
            "php",
            "python_lambda",
            "python",
            "ruby",
        ]

        for lib in libraries:
            manifest_file = manifest_dir / f"{lib}.yml"
            manifest_file.write_text(
                textwrap.dedent(
                    """---
                    manifest:
                      tests/test_file.py::TestClass:
                        - declaration: missing_feature
                    """
                )
            )

        return ManifestEditor(manifests_path=manifest_dir)

    def test_init(self, tmp_path: Path):
        """Test ManifestEditor initialization"""
        editor = self.setup_manifest_editor(tmp_path)
        assert editor.raw_data is not None
        assert "python" in editor.raw_data

    def test_set_context(self, tmp_path: Path):
        """Test setting context on ManifestEditor"""
        editor = self.setup_manifest_editor(tmp_path)
        context = Context.create("python", "3.12.0", "django-poc")
        assert context is not None
        result = editor.set_context(context)
        assert result == editor
        assert editor.context == context

    def test_get_matches(self, tmp_path: Path):
        """Test getting matches for a nodeid"""
        editor = self.setup_manifest_editor(tmp_path)
        context = Context.create("python", "3.12.0", "django-poc")
        assert context is not None
        editor.set_context(context)
        # Try both the exact rule and a child nodeid
        matches_exact = editor.get_matches("tests/test_file.py::TestClass")
        matches_child = editor.get_matches("tests/test_file.py::TestClass::test_method")
        assert isinstance(matches_exact, set)
        assert isinstance(matches_child, set)
        # At least one should have matches (exact match should work)
        assert len(matches_exact) == 1
        assert len(matches_child) == 1

        # Check the content of the views
        view_exact = matches_exact.pop()
        view_child = matches_child.pop()

        # Both should reference the same rule
        assert view_exact.rule == "tests/test_file.py::TestClass"
        assert view_child.rule == "tests/test_file.py::TestClass"

        # Check condition content
        assert view_exact.condition["declaration"] == SkipDeclaration("missing_feature")
        assert view_exact.condition["component"] == "python"
        assert "component_version" not in view_exact.condition
        assert view_child.condition["declaration"] == SkipDeclaration("missing_feature")
        assert view_child.condition["component"] == "python"
        assert "component_version" not in view_child.condition

        # Check other view properties
        assert isinstance(view_exact.condition_index, int)
        assert view_exact.clause_key is None  # No weblog_declaration in the condition
        assert view_exact.is_inline is False  # Condition is a list, not a string
        assert isinstance(view_child.condition_index, int)
        assert view_child.clause_key is None
        assert view_child.is_inline is False

        # Both views should reference the same condition (same rule, same condition index)
        assert view_exact.condition_index == 0
        assert view_child.condition_index == 0

    def test_poke(self, tmp_path: Path):
        """Test poking a view"""
        editor = self.setup_manifest_editor(tmp_path)
        context = Context.create("python", "3.12.0", "django-poc")
        assert context is not None
        editor.set_context(context)
        matches = editor.get_matches("tests/test_file.py::TestClass::test_method")
        assert len(matches) > 0, "No matches found for test nodeid"
        view = matches.pop()
        editor.poke(view)
        assert view in editor.poked_views
        assert context in editor.poked_views[view]

    def test_add_rules(self, tmp_path: Path):
        """Test adding rules"""
        editor = self.setup_manifest_editor(tmp_path)
        context = Context.create("python", "3.12.0", "django-poc")
        assert context is not None
        editor.set_context(context)
        # Try exact match first, fall back to child if needed
        matches = editor.get_matches("tests/test_file.py::TestClass")
        if not matches:
            matches = editor.get_matches("tests/test_file.py::TestClass::test_method")
        assert len(matches) > 0, "No matches found for test nodeid"
        view = matches.pop()
        rules = ["tests/new_test.py", "tests/new_test.py::NewClass"]
        editor.add_rules(rules, view)
        assert "tests/new_test.py" in editor.added_rules
        assert (view, context) in editor.added_rules["tests/new_test.py"]

    def test_compress_pokes(self):
        """Test compressing pokes from multiple contexts"""
        context1 = Context.create("python", "3.12.0", "django-poc")
        context2 = Context.create("python", "3.12.0", "flask-poc")
        assert context1 is not None
        assert context2 is not None
        contexts = {context1, context2}
        version, weblogs = ManifestEditor.compress_pokes(contexts)
        assert version == Version("3.12.0")
        assert isinstance(weblogs, list)
        assert len(weblogs) == 2
        # Check that weblogs contains exactly the expected values (order may vary due to set iteration)
        assert sorted(weblogs) == ["django-poc", "flask-poc"]

    def test_condition_key(self):
        """Test generating condition key"""
        condition: Condition = {
            "declaration": SkipDeclaration("missing_feature"),
            "component": "python",
            "weblog": ["django-poc", "flask-poc"],
        }
        key = ManifestEditor.condition_key(condition)
        assert isinstance(key, tuple)
        # condition_key sorts items alphabetically and converts lists to tuples
        expected_key = (
            ("component", "python"),
            ("declaration", SkipDeclaration("missing_feature")),
            ("weblog", ("django-poc", "flask-poc")),
        )
        assert key == expected_key

    def test_specialize(self, tmp_path: Path):
        """Test specializing a condition for a context"""
        editor = self.setup_manifest_editor(tmp_path)
        context = Context.create("python", "3.12.0", "django-poc")
        assert context is not None
        condition: Condition = {"declaration": SkipDeclaration("missing_feature"), "component": "python"}
        specialized = ManifestEditor.specialize(condition, context)
        assert specialized.get("weblog") == ["django-poc"]
        assert "component_version" in specialized
        # Check that component_version is a SemverRange with the correct value
        assert isinstance(specialized["component_version"], SemverRange)
        assert str(specialized["component_version"]) == ">=3.12.0"

        assert "component_version" not in condition

    @staticmethod
    def _normalize_manifest_data(data):
        """Convert CommentedSeq and other ruamel types to plain Python types for comparison"""
        from ruamel.yaml.comments import CommentedSeq, CommentedMap

        if isinstance(data, CommentedSeq):
            return [Test_ManifestEditor._normalize_manifest_data(item) for item in data]
        if isinstance(data, CommentedMap):
            return {k: Test_ManifestEditor._normalize_manifest_data(v) for k, v in data.items()}
        if isinstance(data, dict):
            return {k: Test_ManifestEditor._normalize_manifest_data(v) for k, v in data.items()}
        if isinstance(data, list):
            return [Test_ManifestEditor._normalize_manifest_data(item) for item in data]
        return data

    def test_poke_inline_condition(self, tmp_path: Path):
        """Test poking an inline condition (string condition)"""
        manifest_dir = tmp_path / "manifests"
        manifest_dir.mkdir()
        python_manifest = manifest_dir / "python.yml"
        python_manifest.write_text(
            textwrap.dedent(
                """---
                manifest:
                  tests/inline_test.py::TestClass: missing_feature
                """
            )
        )
        for lib in ["cpp_httpd", "cpp", "dotnet", "golang", "java", "nodejs", "php", "python_lambda", "ruby"]:
            (manifest_dir / f"{lib}.yml").write_text("---\nmanifest: {}\n")

        editor = ManifestEditor(manifests_path=manifest_dir)
        context = Context.create("python", "3.12.0", "django-poc")
        assert context is not None
        editor.set_context(context)
        editor.poke(editor.get_matches("tests/inline_test.py::TestClass::func").pop())
        editor.write_poke()

        expected = [
            {"declaration": "missing_feature", "excluded_weblog": ["django-poc"]},
            {"declaration": "missing_feature", "weblog": ["django-poc"], "excluded_component_version": ">=3.12.0"},
        ]
        raw_data = editor.raw_data["python"]["manifest"]["tests/inline_test.py::TestClass"]
        assert raw_data == expected

    def test_poke_inline_condition_with_component_version(self, tmp_path: Path):
        """Test poking an inline condition with component_version"""
        manifest_dir = tmp_path / "manifests"
        manifest_dir.mkdir()
        python_manifest = manifest_dir / "python.yml"
        python_manifest.write_text(
            textwrap.dedent(
                """---
                manifest:
                  tests/inline_test.py::TestClass: missing_feature
                """
            )
        )
        for lib in ["cpp_httpd", "cpp", "dotnet", "golang", "java", "nodejs", "php", "python_lambda", "ruby"]:
            (manifest_dir / f"{lib}.yml").write_text("---\nmanifest: {}\n")

        editor = ManifestEditor(manifests_path=manifest_dir)
        context = Context.create("python", "3.12.0", "django-poc")
        assert context is not None
        editor.set_context(context)
        view = editor.get_matches("tests/inline_test.py::TestClass").pop()
        view.condition["component_version"] = SemverRange(">=3.11.0")
        editor.poke(view)
        editor.write_poke()

        expected = [
            {"declaration": "missing_feature", "excluded_weblog": ["django-poc"], "component_version": ">=3.11.0"},
            {
                "declaration": "missing_feature",
                "weblog": ["django-poc"],
                "excluded_component_version": ">=3.12.0",
                "component_version": ">=3.11.0",
            },
        ]
        raw_data = editor.raw_data["python"]["manifest"]["tests/inline_test.py::TestClass"]
        assert raw_data == expected

    def test_poke_weblog_declaration_condition(self, tmp_path: Path):
        """Test poking a condition with weblog_declaration"""
        manifest_dir = tmp_path / "manifests"
        manifest_dir.mkdir()
        python_manifest = manifest_dir / "python.yml"
        python_manifest.write_text(
            textwrap.dedent(
                """---
                manifest:
                  tests/weblog_decl_test.py::TestClass:
                    - declaration: missing_feature
                      component: python
                      weblog_declaration:
                        "*": missing_feature
                        flask-poc: v3.10.0
                """
            )
        )
        for lib in ["cpp_httpd", "cpp", "dotnet", "golang", "java", "nodejs", "php", "python_lambda", "ruby"]:
            (manifest_dir / f"{lib}.yml").write_text("---\nmanifest: {}\n")

        editor = ManifestEditor(manifests_path=manifest_dir)
        context = Context.create("python", "3.12.0", "django-poc")
        assert context is not None
        editor.set_context(context)
        editor.poke(editor.get_matches("tests/weblog_decl_test.py::TestClass").pop())
        editor.write_poke()

        expected = [
            {
                "declaration": "missing_feature",
                "component": "python",
                "weblog_declaration": {"*": "missing_feature", "flask-poc": "v3.10.0", "django-poc": "v3.12.0"},
            }
        ]
        raw_data = editor.raw_data["python"]["manifest"]["tests/weblog_decl_test.py::TestClass"]
        assert raw_data == expected

    def test_poke_normal_condition_without_component_version(self, tmp_path: Path):
        """Test poking a normal condition without component_version"""
        manifest_dir = tmp_path / "manifests"
        manifest_dir.mkdir()
        python_manifest = manifest_dir / "python.yml"
        python_manifest.write_text(
            textwrap.dedent(
                """---
                manifest:
                  tests/normal_test.py::TestClass:
                    - declaration: missing_feature
                """
            )
        )
        for lib in ["cpp_httpd", "cpp", "dotnet", "golang", "java", "nodejs", "php", "python_lambda", "ruby"]:
            (manifest_dir / f"{lib}.yml").write_text("---\nmanifest: {}\n")

        editor = ManifestEditor(manifests_path=manifest_dir)
        context = Context.create("python", "3.12.0", "django-poc")
        assert context is not None
        editor.set_context(context)
        editor.poke(editor.get_matches("tests/normal_test.py::TestClass::func").pop())
        editor.write_poke()

        expected = [
            {"declaration": "missing_feature", "excluded_weblog": ["django-poc"]},
            {"declaration": "missing_feature", "weblog": ["django-poc"], "excluded_component_version": ">=3.12.0"},
        ]
        raw_data = editor.raw_data["python"]["manifest"]["tests/normal_test.py::TestClass"]
        assert raw_data == expected

    def test_poke_normal_condition_with_component_version(self, tmp_path: Path):
        """Test poking a normal condition with component_version"""
        manifest_dir = tmp_path / "manifests"
        manifest_dir.mkdir()
        python_manifest = manifest_dir / "python.yml"
        python_manifest.write_text(
            textwrap.dedent(
                """---
                manifest:
                  tests/normal_test.py::TestClass:
                    - declaration: missing_feature
                      component_version: ">=3.11.0"
                """
            )
        )
        for lib in ["cpp_httpd", "cpp", "dotnet", "golang", "java", "nodejs", "php", "python_lambda", "ruby"]:
            (manifest_dir / f"{lib}.yml").write_text("---\nmanifest: {}\n")

        editor = ManifestEditor(manifests_path=manifest_dir)
        context = Context.create("python", "3.12.0", "django-poc")
        assert context is not None
        editor.set_context(context)
        editor.poke(editor.get_matches("tests/normal_test.py::TestClass").pop())
        editor.write_poke()

        expected = [
            {
                "declaration": "missing_feature",
                "component_version": ">=3.11.0",
                "excluded_weblog": ["django-poc"],
            },
            {"declaration": "missing_feature", "weblog": ["django-poc"], "excluded_component_version": ">=3.12.0"},
        ]
        raw_data = editor.raw_data["python"]["manifest"]["tests/normal_test.py::TestClass"]
        assert raw_data == expected

    def test_poke_normal_condition_with_weblog(self, tmp_path: Path):
        """Test poking a normal condition that already has weblog"""
        manifest_dir = tmp_path / "manifests"
        manifest_dir.mkdir()
        python_manifest = manifest_dir / "python.yml"
        python_manifest.write_text(
            textwrap.dedent(
                """---
                manifest:
                  tests/normal_test.py::TestClass:
                    - declaration: missing_feature
                      weblog: ["django-poc"]
                """
            )
        )
        for lib in ["cpp_httpd", "cpp", "dotnet", "golang", "java", "nodejs", "php", "python_lambda", "ruby"]:
            (manifest_dir / f"{lib}.yml").write_text("---\nmanifest: {}\n")

        editor = ManifestEditor(manifests_path=manifest_dir)
        context = Context.create("python", "3.12.0", "django-poc")
        assert context is not None
        editor.set_context(context)
        editor.poke(editor.get_matches("tests/normal_test.py::TestClass").pop())
        editor.write_poke()

        expected = [
            {
                "declaration": "missing_feature",
                "weblog": ["django-poc"],
                "excluded_weblog": ["django-poc"],
            },
            {"declaration": "missing_feature", "weblog": ["django-poc"], "excluded_component_version": ">=3.12.0"},
        ]
        raw_data = editor.raw_data["python"]["manifest"]["tests/normal_test.py::TestClass"]
        assert raw_data == expected
        normalized = self._normalize_manifest_data(raw_data)
        # Sort excluded_weblog lists for comparison since order may vary
        normalized[0]["excluded_weblog"] = sorted(normalized[0]["excluded_weblog"])
        expected[0]["excluded_weblog"] = sorted(expected[0]["excluded_weblog"])
        assert normalized == expected


@scenarios.test_the_test
@features.not_reported
class Test_EndToEnd_Activation:
    """End-to-end test of the activation mechanism excluding argument parsing and artifact download"""

    def setup_artifact_data(self, tmp_path: Path) -> Path:
        """Create realistic artifact data structure with multiple scenarios and test outcomes"""
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        # parse_artifact_data expects: data_dir/directory/scenario_dir/report.json
        # So we need a parent directory for each scenario
        parent_dir = data_dir / "normal_directory"
        parent_dir.mkdir()

        # Create multiple scenario directories with different contexts
        scenarios_data = [
            {
                "dir": "python_3.12.0_django-poc",
                "context": {
                    "library_name": "python",
                    "library": "3.12.0",
                    "weblog_variant": "django-poc",
                },
                "tests": [
                    {
                        "nodeid": "tests/appsec/test_waf.py::Test_WAF_Rules::test_sql_injection",
                        "outcome": "xpassed",
                    },
                    {
                        "nodeid": "tests/appsec/test_waf.py::Test_WAF_Rules::test_xss",
                        "outcome": "xpassed",
                    },
                    {
                        "nodeid": "tests/appsec/test_waf.py::Test_WAF_Rules::test_path_traversal",
                        "outcome": "xfailed",
                    },
                    {
                        "nodeid": "tests/appsec/test_waf.py::Test_WAF_Rules::test_csrf",
                        "outcome": "passed",
                    },
                ],
            },
            {
                "dir": "python_3.12.0_flask-poc",
                "context": {
                    "library_name": "python",
                    "library": "3.12.0",
                    "weblog_variant": "flask-poc",
                },
                "tests": [
                    {
                        "nodeid": "tests/appsec/test_waf.py::Test_WAF_Rules::test_sql_injection",
                        "outcome": "xpassed",
                    },
                ],
            },
            {
                "dir": "java_1.8.0_spring-boot",
                "context": {
                    "library_name": "java",
                    "library": "1.8.0",
                    "weblog_variant": "spring-boot",
                },
                "tests": [
                    {
                        "nodeid": "tests/appsec/test_waf.py::Test_WAF_Rules::test_sql_injection",
                        "outcome": "xpassed",
                    },
                ],
            },
        ]

        for scenario in scenarios_data:
            # Create scenario directory under parent_dir
            scenario_dir = parent_dir / scenario["dir"]
            scenario_dir.mkdir()

            report = {
                "context": scenario["context"],
                "tests": scenario["tests"],
            }

            report_file = scenario_dir / "report.json"
            report_file.write_text(json.dumps(report, indent=2))

        return data_dir

    def setup_manifests(self, tmp_path: Path) -> Path:
        """Create manifest files with existing rules"""
        manifest_dir = tmp_path / "manifests"
        manifest_dir.mkdir()

        # Python manifest with existing rule
        python_manifest = manifest_dir / "python.yml"
        python_manifest.write_text(
            textwrap.dedent(
                """---
                manifest:
                  tests/appsec/test_waf.py::Test_WAF_Rules:
                    - declaration: missing_feature
                """
            )
        )

        # Java manifest with existing rule
        java_manifest = manifest_dir / "java.yml"
        java_manifest.write_text(
            textwrap.dedent(
                """---
                manifest:
                  tests/appsec/test_waf.py::Test_WAF_Rules:
                    - declaration: missing_feature
                """
            )
        )

        # Create empty manifests for other libraries
        libraries = [
            "cpp_httpd",
            "cpp",
            "dotnet",
            "golang",
            "nodejs",
            "php",
            "python_lambda",
            "ruby",
        ]

        for lib in libraries:
            manifest_file = manifest_dir / f"{lib}.yml"
            manifest_file.write_text("---\nmanifest: {}\n")

        return manifest_dir

    def test_end_to_end_activation_flow(self, tmp_path: Path):
        """Test the complete activation flow: parse artifact -> update manifest -> verify results"""
        # Setup artifact data (simulating already downloaded data)
        data_dir = self.setup_artifact_data(tmp_path)

        # Setup manifest files
        manifest_dir = self.setup_manifests(tmp_path)

        # Step 1: Parse artifact data (simulating what happens after download)
        test_data, weblogs = parse_artifact_data(data_dir, ["python", "java"])

        # Verify parsing worked
        assert len(test_data) > 0
        assert "python" in weblogs
        assert "java" in weblogs
        assert "django-poc" in weblogs["python"]
        assert "flask-poc" in weblogs["python"]
        assert "spring-boot" in weblogs["java"]

        # Verify test data structure
        python_context = Context.create("python", "3.12.0", "django-poc")
        assert python_context is not None
        assert python_context in test_data

        python_test_data = test_data[python_context]
        assert len(python_test_data.xpass_nodes) == 2  # Two xpassed tests
        assert "tests/appsec/test_waf.py::Test_WAF_Rules::test_sql_injection" in python_test_data.xpass_nodes
        assert "tests/appsec/test_waf.py::Test_WAF_Rules::test_xss" in python_test_data.xpass_nodes

        # Step 2: Create manifest editor
        editor = ManifestEditor(manifests_path=manifest_dir)

        # Verify that get_matches can find rules for our test nodeids
        # This ensures the manifest setup is correct
        python_django_context = Context.create("python", "3.12.0", "django-poc")
        assert python_django_context is not None
        editor.set_context(python_django_context)
        matches = editor.get_matches("tests/appsec/test_waf.py::Test_WAF_Rules::test_sql_injection")
        assert len(matches) > 0, "Expected to find matching rules in manifest"

        # Step 3: Update manifest (the core activation logic)
        # This should process all xpassed nodes and update the manifest accordingly
        update_manifest(editor, test_data)

        # Step 4: Verify results
        # Verify that poked_views were populated for xpassed tests
        # Since we verified matches exist above, poked_views should be populated
        assert len(editor.poked_views) > 0, "Expected poked_views to be populated after update_manifest"

        # Verify that views were poked for the correct contexts
        python_django_context = Context.create("python", "3.12.0", "django-poc")
        python_flask_context = Context.create("python", "3.12.0", "flask-poc")
        java_context = Context.create("java", "1.8.0", "spring-boot")

        assert python_django_context is not None
        assert python_flask_context is not None
        assert java_context is not None

        # Check that contexts were added to poked_views
        poked_contexts = set()
        for view, contexts in editor.poked_views.items():
            poked_contexts.update(contexts)
            # Verify the view corresponds to a rule we expect
            if "tests/appsec/test_waf.py::Test_WAF_Rules" in view.rule:
                # Verify our contexts are in the poked contexts for this view
                assert any(ctx in (python_django_context, python_flask_context, java_context) for ctx in contexts), (
                    f"Expected one of our contexts to be in poked contexts for view {view.rule}"
                )

        # Verify at least one of our contexts was poked
        assert (
            python_django_context in poked_contexts
            or python_flask_context in poked_contexts
            or java_context in poked_contexts
        ), "Expected at least one of our test contexts to be in poked_contexts"

        # Verify that added_rules were populated for xfailed tests (deactivation rules)
        # The xfailed test should trigger add_rules via get_deactivation
        # Note: added_rules will only be populated if the trie traversal finds XFAIL nodes
        # that match the rule path. This depends on the trie structure and traversal logic.
        # Since we have an xfailed test in the trie, rules should be added
        assert len(editor.added_rules) > 0, "Expected added_rules to be populated for xfailed tests"

        # Step 5: Verify manifest editor can write (without actually writing)
        # This tests that the internal state is consistent
        assert editor.raw_data is not None
        assert "python" in editor.raw_data
        assert "java" in editor.raw_data

    def test_end_to_end_with_multiple_libraries(self, tmp_path: Path):
        """Test end-to-end flow with multiple libraries and complex scenarios"""
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        # parse_artifact_data expects: data_dir/directory/scenario_dir/report.json
        parent_dir = data_dir / "normal_directory"
        parent_dir.mkdir()

        # Create scenarios for multiple libraries
        scenarios = [
            {
                "dir": "python_2.5.0_django-poc",
                "context": {"library_name": "python", "library": "2.5.0", "weblog_variant": "django-poc"},
                "tests": [
                    {"nodeid": "tests/parametric/test_sampling.py::Test_Sampling::test_basic", "outcome": "xpassed"}
                ],
            },
            {
                "dir": "nodejs_3.0.0_express4",
                "context": {"library_name": "nodejs", "library": "3.0.0", "weblog_variant": "express4"},
                "tests": [
                    {"nodeid": "tests/parametric/test_sampling.py::Test_Sampling::test_basic", "outcome": "xpassed"}
                ],
            },
        ]

        for scenario in scenarios:
            scenario_dir = parent_dir / scenario["dir"]
            scenario_dir.mkdir()
            report_file = scenario_dir / "report.json"
            report_file.write_text(json.dumps({"context": scenario["context"], "tests": scenario["tests"]}, indent=2))

        # Setup manifests
        manifest_dir = tmp_path / "manifests"
        manifest_dir.mkdir()

        for lib in ["python", "nodejs"] + [
            "cpp_httpd",
            "cpp",
            "dotnet",
            "golang",
            "java",
            "php",
            "python_lambda",
            "ruby",
        ]:
            manifest_file = manifest_dir / f"{lib}.yml"
            if lib in ["python", "nodejs"]:
                manifest_file.write_text(
                    textwrap.dedent(
                        f"""---
                        manifest:
                          tests/parametric/test_sampling.py::Test_Sampling:
                            - declaration: missing_feature
                        """
                    )
                )
            else:
                manifest_file.write_text("---\nmanifest: {}\n")

        # Parse and update
        test_data, weblogs = parse_artifact_data(data_dir, ["python", "nodejs"])
        assert len(test_data) == 2

        editor = ManifestEditor(manifests_path=manifest_dir)
        update_manifest(editor, test_data)

        # Verify both libraries were processed
        assert len(editor.poked_views) > 0
        poked_libraries = set()
        for view, contexts in editor.poked_views.items():
            for ctx in contexts:
                poked_libraries.add(ctx.library)

        assert "python" in poked_libraries
        assert "nodejs" in poked_libraries
