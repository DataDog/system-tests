import json
import tempfile
from pathlib import Path

import pytest
import yaml

from utils.scripts.activate_easy_wins._internal.test_artifact import (
    ActivationStatus,
    parse_artifact_data,
)
from utils.scripts.activate_easy_wins._internal.manifest_editor import ManifestEditor
from utils.scripts.activate_easy_wins._internal.core import update_manifest


pytestmark = pytest.mark.scenario("TEST_THE_TEST")


def create_report_json(
    library_name: str,
    library_version: str,
    weblog_variant: str,
    tests: list[dict],
) -> dict:
    """Helper to create report.json content."""
    return {
        "context": {
            "library_name": library_name,
            "library": library_version,
            "weblog_variant": weblog_variant,
        },
        "tests": tests,
    }


def create_manifest_yaml(rules: dict[str, str]) -> str:
    """Helper to create manifest YAML content."""
    lines = ["---", "manifest:"]
    for rule, declaration in sorted(rules.items()):
        lines.append(f"  {rule}: {declaration}")
    return "\n".join(lines) + "\n"


# =============================================================================
# Tests for parse_artifact_data function
# =============================================================================


def test_parse_artifact_data_xpassed_tests():
    """Test that xpassed tests are correctly tracked in xpass_nodes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        scenario_dir = data_dir / "test_run" / "scenario1"
        scenario_dir.mkdir(parents=True)

        report = create_report_json(
            library_name="python",
            library_version="2.0.0",
            weblog_variant="flask",
            tests=[
                {"nodeid": "tests/test_module.py::Test_Class::test_method", "outcome": "xpassed"},
                {"nodeid": "tests/test_module.py::Test_Class::test_other", "outcome": "passed"},
            ],
        )
        with (scenario_dir / "report.json").open("w") as f:
            json.dump(report, f)

        test_data, weblogs = parse_artifact_data(data_dir, ["python"])

        assert len(test_data) == 1
        context = next(iter(test_data.keys()))
        assert context.library == "python"
        assert "tests/test_module.py::Test_Class::test_method" in test_data[context].xpass_nodes
        assert "tests/test_module.py::Test_Class::test_other" not in test_data[context].xpass_nodes
        assert weblogs["python"] == {"flask"}


def test_parse_artifact_data_xfailed_tests():
    """Test that xfailed tests result in XFAIL status in trie."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        scenario_dir = data_dir / "test_run" / "scenario1"
        scenario_dir.mkdir(parents=True)

        report = create_report_json(
            library_name="java",
            library_version="1.5.0",
            weblog_variant="spring-boot",
            tests=[
                {"nodeid": "tests/test_feature.py::Test_Feature::test_xfail", "outcome": "xfailed"},
            ],
        )
        with (scenario_dir / "report.json").open("w") as f:
            json.dump(report, f)

        test_data, weblogs = parse_artifact_data(data_dir, ["java"])

        assert len(test_data) == 1
        context = next(iter(test_data.keys()))
        assert context.library == "java"
        assert test_data[context].trie.get("tests/test_feature.py/Test_Feature/test_xfail") == ActivationStatus.XFAIL
        assert weblogs["java"] == {"spring-boot"}


def test_parse_artifact_data_excluded_owners():
    """Test that xpassed tests with excluded owners are treated as xfailed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        scenario_dir = data_dir / "test_run" / "scenario1"
        scenario_dir.mkdir(parents=True)

        report = create_report_json(
            library_name="nodejs",
            library_version="3.0.0",
            weblog_variant="express",
            tests=[
                {
                    "nodeid": "tests/test_excluded.py::Test_Excluded::test_skip",
                    "outcome": "xpassed",
                    "metadata": {"owners": ["@excluded-team"]},
                },
                {
                    "nodeid": "tests/test_included.py::Test_Included::test_keep",
                    "outcome": "xpassed",
                    "metadata": {"owners": ["@included-team"]},
                },
            ],
        )
        with (scenario_dir / "report.json").open("w") as f:
            json.dump(report, f)

        test_data, _ = parse_artifact_data(data_dir, ["nodejs"], excluded_owners={"@excluded-team"})

        context = next(iter(test_data.keys()))
        # The excluded owner test should not be in xpass_nodes
        assert "tests/test_excluded.py::Test_Excluded::test_skip" not in test_data[context].xpass_nodes
        # The included owner test should be in xpass_nodes
        assert "tests/test_included.py::Test_Included::test_keep" in test_data[context].xpass_nodes


def test_parse_artifact_data_missing_report():
    """Test that missing report.json files are gracefully skipped."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        # Create a scenario directory without report.json
        scenario_dir = data_dir / "test_run" / "scenario_no_report"
        scenario_dir.mkdir(parents=True)

        test_data, weblogs = parse_artifact_data(data_dir, ["python"])

        assert len(test_data) == 0
        assert len(weblogs) == 0


def test_parse_artifact_data_library_filter():
    """Test that only specified libraries are included in results."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)

        # Create reports for two different libraries
        python_dir = data_dir / "python_run" / "scenario1"
        python_dir.mkdir(parents=True)
        python_report = create_report_json(
            library_name="python",
            library_version="2.0.0",
            weblog_variant="flask",
            tests=[{"nodeid": "tests/test_py.py::test_python", "outcome": "xpassed"}],
        )
        with (python_dir / "report.json").open("w") as f:
            json.dump(python_report, f)

        ruby_dir = data_dir / "ruby_run" / "scenario1"
        ruby_dir.mkdir(parents=True)
        ruby_report = create_report_json(
            library_name="ruby",
            library_version="1.0.0",
            weblog_variant="rails",
            tests=[{"nodeid": "tests/test_rb.py::test_ruby", "outcome": "xpassed"}],
        )
        with (ruby_dir / "report.json").open("w") as f:
            json.dump(ruby_report, f)

        # Filter to only python
        test_data, weblogs = parse_artifact_data(data_dir, ["python"])

        assert len(test_data) == 1
        context = next(iter(test_data.keys()))
        assert context.library == "python"
        assert "ruby" not in weblogs
        assert "python" in weblogs


def test_parse_artifact_data_trie_none_status_on_mixed_outcomes():
    """Test that trie nodes get NONE status when children have mixed outcomes.

    The trie uses NONE to indicate that a parent node cannot be activated at that level
    because its children have conflicting outcomes (e.g., some xpassed and some xfailed).
    This prevents activating an entire class/file when only some tests pass.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        scenario_dir = data_dir / "test_run" / "scenario1"
        scenario_dir.mkdir(parents=True)

        # Create tests with mixed outcomes under the same class and directory
        report = create_report_json(
            library_name="python",
            library_version="2.0.0",
            weblog_variant="flask",
            tests=[
                # Class with mixed outcomes - should result in NONE at class level
                {"nodeid": "tests/appsec/test_mixed.py::Test_Mixed::test_passes", "outcome": "xpassed"},
                {"nodeid": "tests/appsec/test_mixed.py::Test_Mixed::test_fails", "outcome": "xfailed"},
                # Class with all xpassed - should result in XPASS at class level
                {"nodeid": "tests/appsec/test_all_pass.py::Test_AllPass::test_one", "outcome": "xpassed"},
                {"nodeid": "tests/appsec/test_all_pass.py::Test_AllPass::test_two", "outcome": "xpassed"},
                # Class with all xfailed - should result in XFAIL at class level
                {"nodeid": "tests/appsec/test_all_fail.py::Test_AllFail::test_a", "outcome": "xfailed"},
                {"nodeid": "tests/appsec/test_all_fail.py::Test_AllFail::test_b", "outcome": "xfailed"},
            ],
        )
        with (scenario_dir / "report.json").open("w") as f:
            json.dump(report, f)

        test_data, _ = parse_artifact_data(data_dir, ["python"])

        context = next(iter(test_data.keys()))
        trie = test_data[context].trie

        # Test_Mixed class should be NONE because it has both xpassed and xfailed children
        assert trie.get("tests/appsec/test_mixed.py/Test_Mixed") == ActivationStatus.NONE
        # Individual test methods should have their own status
        assert trie.get("tests/appsec/test_mixed.py/Test_Mixed/test_passes") == ActivationStatus.XPASS
        assert trie.get("tests/appsec/test_mixed.py/Test_Mixed/test_fails") == ActivationStatus.XFAIL

        # Test_AllPass class should be XPASS because all children xpassed
        assert trie.get("tests/appsec/test_all_pass.py/Test_AllPass") == ActivationStatus.XPASS
        assert trie.get("tests/appsec/test_all_pass.py/Test_AllPass/test_one") == ActivationStatus.XPASS
        assert trie.get("tests/appsec/test_all_pass.py/Test_AllPass/test_two") == ActivationStatus.XPASS

        # Test_AllFail class should be XFAIL because all children xfailed
        assert trie.get("tests/appsec/test_all_fail.py/Test_AllFail") == ActivationStatus.XFAIL
        assert trie.get("tests/appsec/test_all_fail.py/Test_AllFail/test_a") == ActivationStatus.XFAIL
        assert trie.get("tests/appsec/test_all_fail.py/Test_AllFail/test_b") == ActivationStatus.XFAIL

        # File levels should reflect their content
        assert trie.get("tests/appsec/test_mixed.py") == ActivationStatus.NONE
        assert trie.get("tests/appsec/test_all_pass.py") == ActivationStatus.XPASS
        assert trie.get("tests/appsec/test_all_fail.py") == ActivationStatus.XFAIL

        # Directory level should be NONE because it contains mixed file outcomes
        assert trie.get("tests/appsec") == ActivationStatus.NONE
        assert trie.get("tests") == ActivationStatus.NONE


def test_parse_artifact_data_parametric_tests_mixed_params_not_activated():
    """Test that parametric tests with mixed outcomes across parameters are not activated.

    When a test method has parameters (e.g., test_method[param1], test_method[param2]),
    and some parameters pass while others fail, the test method should get XFAIL status
    to prevent activation. The parameter brackets [...] should be stripped from trie keys -
    rules in manifests should not contain the parameter part.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        scenario_dir = data_dir / "test_run" / "scenario1"
        scenario_dir.mkdir(parents=True)

        # Create parametric tests with mixed outcomes across parameters
        report = create_report_json(
            library_name="python",
            library_version="2.0.0",
            weblog_variant="flask",
            tests=[
                # Same test method with different parameters - mixed outcomes
                {"nodeid": "tests/parametric/test_params.py::Test_Params::test_mixed[param1]", "outcome": "xpassed"},
                {"nodeid": "tests/parametric/test_params.py::Test_Params::test_mixed[param2]", "outcome": "xfailed"},
                {"nodeid": "tests/parametric/test_params.py::Test_Params::test_mixed[param3]", "outcome": "xpassed"},
                # Same test method with all parameters passing
                {"nodeid": "tests/parametric/test_params.py::Test_Params::test_all_pass[a]", "outcome": "xpassed"},
                {"nodeid": "tests/parametric/test_params.py::Test_Params::test_all_pass[b]", "outcome": "xpassed"},
                {"nodeid": "tests/parametric/test_params.py::Test_Params::test_all_pass[c]", "outcome": "xpassed"},
                # Same test method with all parameters failing
                {"nodeid": "tests/parametric/test_params.py::Test_Params::test_all_fail[x]", "outcome": "xfailed"},
                {"nodeid": "tests/parametric/test_params.py::Test_Params::test_all_fail[y]", "outcome": "xfailed"},
            ],
        )
        with (scenario_dir / "report.json").open("w") as f:
            json.dump(report, f)

        test_data, _ = parse_artifact_data(data_dir, ["python"])

        context = next(iter(test_data.keys()))
        trie = test_data[context].trie

        # Verify parameter brackets are stripped - keys should NOT contain [...]
        all_keys = list(trie.keys())
        for key in all_keys:
            assert "[" not in key, f"Trie key should not contain parameter brackets: {key}"
            assert "]" not in key, f"Trie key should not contain parameter brackets: {key}"

        # test_mixed should be XFAIL because some parameters failed - test should not be activated
        assert trie.get("tests/parametric/test_params.py/Test_Params/test_mixed") == ActivationStatus.XFAIL

        # test_all_pass should be XPASS because all parameters passed
        assert trie.get("tests/parametric/test_params.py/Test_Params/test_all_pass") == ActivationStatus.XPASS

        # test_all_fail should be XFAIL because all parameters failed
        assert trie.get("tests/parametric/test_params.py/Test_Params/test_all_fail") == ActivationStatus.XFAIL

        # Class level should be NONE because it contains tests that should not be activated
        assert trie.get("tests/parametric/test_params.py/Test_Params") == ActivationStatus.NONE

        # Verify xpass_nodes contain the full nodeid WITH parameters (for tracking)
        # but trie keys are WITHOUT parameters (for manifest rules)
        assert "tests/parametric/test_params.py::Test_Params::test_mixed" in test_data[context].xpass_nodes
        assert "tests/parametric/test_params.py::Test_Params::test_mixed" in test_data[context].xpass_nodes
        assert "tests/parametric/test_params.py::Test_Params::test_all_pass" in test_data[context].xpass_nodes


# =============================================================================
# End-to-end tests for the activation process
# =============================================================================


def test_e2e_activation_modifies_manifest():
    """Test that full activation process correctly modifies manifest for xpassed tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "data"
        manifest_dir = Path(tmpdir) / "manifests"
        data_dir.mkdir()
        manifest_dir.mkdir()

        # Create artifact data with xpassed test
        scenario_dir = data_dir / "ruby_run" / "scenario1"
        scenario_dir.mkdir(parents=True)
        report = create_report_json(
            library_name="ruby",
            library_version="2.5.0",
            weblog_variant="rails70",
            tests=[
                {"nodeid": "tests/appsec/test_feature.py::Test_Feature::test_method", "outcome": "xpassed"},
            ],
        )
        with (scenario_dir / "report.json").open("w") as f:
            json.dump(report, f)

        # Create manifest with missing_feature rule
        manifest_content = create_manifest_yaml(
            {
                "tests/appsec/test_feature.py::Test_Feature": "missing_feature",
            }
        )
        (manifest_dir / "ruby.yml").write_text(manifest_content)

        # Run activation
        test_data, weblogs = parse_artifact_data(data_dir, ["ruby"])
        manifest_editor = ManifestEditor(weblogs, manifests_path=manifest_dir, components=["ruby"])
        tests_per_language, modified_rules, created_rules, _, _, _ = update_manifest(manifest_editor, test_data)

        # Verify activation occurred
        assert tests_per_language.get("ruby", 0) > 0
        assert sum(modified_rules.values()) > 0 or created_rules > 0


def test_e2e_activation_filters_by_component():
    """Test that activation only processes specified components."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "data"
        manifest_dir = Path(tmpdir) / "manifests"
        data_dir.mkdir()
        manifest_dir.mkdir()

        # Create artifact data for multiple libraries
        for lib_name, weblog in [("ruby", "rails70"), ("python", "flask")]:
            scenario_dir = data_dir / f"{lib_name}_run" / "scenario1"
            scenario_dir.mkdir(parents=True)
            report = create_report_json(
                library_name=lib_name,
                library_version="2.0.0",
                weblog_variant=weblog,
                tests=[{"nodeid": f"tests/test_{lib_name}.py::Test_Class::test_method", "outcome": "xpassed"}],
            )
            with (scenario_dir / "report.json").open("w") as f:
                json.dump(report, f)

        # Create manifests
        for lib_name in ["ruby", "python"]:
            manifest_content = create_manifest_yaml(
                {
                    f"tests/test_{lib_name}.py::Test_Class": "missing_feature",
                }
            )
            (manifest_dir / f"{lib_name}.yml").write_text(manifest_content)

        # Run activation with only ruby
        test_data, weblogs = parse_artifact_data(data_dir, ["ruby"])
        manifest_editor = ManifestEditor(weblogs, manifests_path=manifest_dir, components=["ruby"])
        tests_per_language, _, _, _, _, _ = update_manifest(manifest_editor, test_data)

        # Verify only ruby was processed
        assert "ruby" in tests_per_language
        assert "python" not in tests_per_language


def test_e2e_activation_excludes_owners():
    """Test that tests owned by excluded teams are not activated."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "data"
        manifest_dir = Path(tmpdir) / "manifests"
        data_dir.mkdir()
        manifest_dir.mkdir()

        # Create artifact data with tests from different owners
        scenario_dir = data_dir / "ruby_run" / "scenario1"
        scenario_dir.mkdir(parents=True)
        report = create_report_json(
            library_name="ruby",
            library_version="2.5.0",
            weblog_variant="rails70",
            tests=[
                {
                    "nodeid": "tests/excluded/test_excluded.py::Test_Excluded::test_one",
                    "outcome": "xpassed",
                    "metadata": {"owners": ["@DataDog/excluded-team"]},
                },
                {
                    "nodeid": "tests/included/test_included.py::Test_Included::test_two",
                    "outcome": "xpassed",
                    "metadata": {"owners": ["@DataDog/included-team"]},
                },
            ],
        )
        with (scenario_dir / "report.json").open("w") as f:
            json.dump(report, f)

        # Create manifest
        manifest_content = create_manifest_yaml(
            {
                "tests/excluded/test_excluded.py::Test_Excluded": "missing_feature",
                "tests/included/test_included.py::Test_Included": "missing_feature",
            }
        )
        (manifest_dir / "ruby.yml").write_text(manifest_content)

        # Run activation with excluded owner
        test_data, weblogs = parse_artifact_data(data_dir, ["ruby"], excluded_owners={"@DataDog/excluded-team"})
        manifest_editor = ManifestEditor(weblogs, manifests_path=manifest_dir, components=["ruby"])
        tests_per_language, _, _, _, unique_tests, _ = update_manifest(manifest_editor, test_data)

        # Verify only one test was activated (the included one)
        assert tests_per_language.get("ruby", 0) == 1
        assert unique_tests.get("ruby", 0) == 1


def test_e2e_activation_tracks_activations_per_owner():
    """Test that activations are correctly tracked per code owner."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "data"
        manifest_dir = Path(tmpdir) / "manifests"
        data_dir.mkdir()
        manifest_dir.mkdir()

        # Create artifact data with tests from multiple owners
        scenario_dir = data_dir / "ruby_run" / "scenario1"
        scenario_dir.mkdir(parents=True)
        report = create_report_json(
            library_name="ruby",
            library_version="2.5.0",
            weblog_variant="rails70",
            tests=[
                {
                    "nodeid": "tests/team_a/test_a1.py::Test_A1::test_one",
                    "outcome": "xpassed",
                    "metadata": {"owners": ["@DataDog/team-a"]},
                },
                {
                    "nodeid": "tests/team_a/test_a2.py::Test_A2::test_two",
                    "outcome": "xpassed",
                    "metadata": {"owners": ["@DataDog/team-a"]},
                },
                {
                    "nodeid": "tests/team_b/test_b1.py::Test_B1::test_three",
                    "outcome": "xpassed",
                    "metadata": {"owners": ["@DataDog/team-b"]},
                },
            ],
        )
        with (scenario_dir / "report.json").open("w") as f:
            json.dump(report, f)

        # Create manifest
        manifest_content = create_manifest_yaml(
            {
                "tests/team_a/test_a1.py::Test_A1": "missing_feature",
                "tests/team_a/test_a2.py::Test_A2": "missing_feature",
                "tests/team_b/test_b1.py::Test_B1": "missing_feature",
            }
        )
        (manifest_dir / "ruby.yml").write_text(manifest_content)

        # Run activation
        test_data, weblogs = parse_artifact_data(data_dir, ["ruby"])
        manifest_editor = ManifestEditor(weblogs, manifests_path=manifest_dir, components=["ruby"])
        _, _, _, _, _, activations_per_owner = update_manifest(manifest_editor, test_data)

        # Verify owner tracking
        assert activations_per_owner.get("@DataDog/team-a", 0) == 2
        assert activations_per_owner.get("@DataDog/team-b", 0) == 1


def test_e2e_activation_handles_mixed_outcomes():
    """Test activation with mixed xpassed and xfailed outcomes for same test class."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "data"
        manifest_dir = Path(tmpdir) / "manifests"
        data_dir.mkdir()
        manifest_dir.mkdir()

        # Create artifact data with mixed outcomes
        scenario_dir = data_dir / "ruby_run" / "scenario1"
        scenario_dir.mkdir(parents=True)
        report = create_report_json(
            library_name="ruby",
            library_version="2.5.0",
            weblog_variant="rails70",
            tests=[
                {"nodeid": "tests/mixed/test_mixed.py::Test_Mixed::test_passes", "outcome": "xpassed"},
                {"nodeid": "tests/mixed/test_mixed.py::Test_Mixed::test_fails", "outcome": "xfailed"},
                {"nodeid": "tests/passing/test_all_pass.py::Test_AllPass::test_one", "outcome": "xpassed"},
                {"nodeid": "tests/passing/test_all_pass.py::Test_AllPass::test_two", "outcome": "xpassed"},
            ],
        )
        with (scenario_dir / "report.json").open("w") as f:
            json.dump(report, f)

        # Create manifest
        manifest_content = create_manifest_yaml(
            {
                "tests/mixed/test_mixed.py::Test_Mixed": "missing_feature",
                "tests/passing/test_all_pass.py::Test_AllPass": "missing_feature",
            }
        )
        (manifest_dir / "ruby.yml").write_text(manifest_content)

        # Run activation
        test_data, weblogs = parse_artifact_data(data_dir, ["ruby"])
        manifest_editor = ManifestEditor(weblogs, manifests_path=manifest_dir, components=["ruby"])
        tests_per_language, _modified_rules, _, _, unique_tests, _ = update_manifest(manifest_editor, test_data)

        # Verify: xpassed tests are tracked
        assert tests_per_language.get("ruby", 0) == 3  # 3 xpassed tests
        assert unique_tests.get("ruby", 0) == 3

        # Verify trie has correct status (class level should be NONE due to mixed outcomes)
        context = next(iter(test_data.keys()))
        # The mixed class should have NONE status because it has both xpass and xfail
        assert test_data[context].trie.get("tests/mixed/test_mixed.py/Test_Mixed") == ActivationStatus.NONE
        # The all-pass class should have XPASS status
        assert test_data[context].trie.get("tests/passing/test_all_pass.py/Test_AllPass") == ActivationStatus.XPASS


def test_manifest_editor_add_condition_to_function_level_inline_declaration():
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "data"
        manifest_dir = Path(tmpdir) / "manifests"
        data_dir.mkdir()
        manifest_dir.mkdir()

        scenario_dir = data_dir / "python_flask_run" / "scenario1"
        scenario_dir.mkdir(parents=True)
        report = create_report_json(
            library_name="python",
            library_version="2.5.0",
            weblog_variant="flask",
            tests=[
                {"nodeid": "tests/appsec/test_feature.py::Test_Feature::test_method", "outcome": "xpassed"},
                {"nodeid": "tests/appsec/test_feature.py::Test_Feature::test_method2", "outcome": "xfailed"},
            ],
        )
        with (scenario_dir / "report.json").open("w") as f:
            json.dump(report, f)
        scenario_dir = data_dir / "python_django_run" / "scenario1"
        scenario_dir.mkdir(parents=True)
        report = create_report_json(
            library_name="python",
            library_version="2.5.0",
            weblog_variant="django",
            tests=[],
        )
        with (scenario_dir / "report.json").open("w") as f:
            json.dump(report, f)

        manifest_content = """---
manifest:
  tests/appsec/test_feature.py::Test_Feature: missing_feature
  tests/appsec/test_feature.py::Test_Feature::test_method2: bug (XXXX)
"""
        (manifest_dir / "python.yml").write_text(manifest_content)

        test_data, weblogs = parse_artifact_data(data_dir, ["python"])
        manifest_editor = ManifestEditor(weblogs, manifests_path=manifest_dir, components=["python"])
        update_manifest(manifest_editor, test_data)

        manifest_editor.write(manifest_dir)

        with (manifest_dir / "python.yml").open() as f:
            result = yaml.safe_load(f)

        rule = result["manifest"].get("tests/appsec/test_feature.py::Test_Feature::test_method2")
        assert rule == [{"declaration": "bug (XXXX)"}, {"weblog_declaration": {"flask": "missing_feature"}}]
