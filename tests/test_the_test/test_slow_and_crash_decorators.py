import shutil
import textwrap
from pathlib import Path

import pytest

from utils import bug, missing_feature, scenarios, features, slow, scenario_crash

from .utils import run_system_tests

FILENAME = "tests/test_the_test/test_slow_and_crash_decorators.py"


@scenarios.test_the_test
class Test_SlowDecorator:
    """Test that the @slow decorator skips tests only when combined with a declaration."""

    def test_slow_alone_runs_normally(self):
        """Test that @slow alone does not skip the test."""
        tests = run_system_tests(test_path=FILENAME)

        nodeid = f"{FILENAME}::Test_SlowMock::test_slow_alone"
        assert tests[nodeid]["outcome"] == "passed"

    def test_slow_with_declaration_is_skipped(self):
        """Test that @slow combined with a declaration skips the test."""
        tests = run_system_tests(test_path=FILENAME)

        nodeid = f"{FILENAME}::Test_SlowMock::test_slow_with_bug"
        assert tests[nodeid]["outcome"] == "skipped"

    def test_slow_with_manifest_declaration_is_skipped(self):
        """Test that @slow combined with a manifest declaration results in skip.

        This test verifies that when a manifest declares a test as missing_feature,
        and the test has @slow decorator, the combination triggers the skip_if_xfail logic.
        """
        manifest_file = Path("manifests/java.yml")
        backup_file = Path("manifests/java.yml.backup")

        # Move original manifest to backup
        shutil.move(manifest_file, backup_file)

        try:
            # Create a manifest file that declares our mock test as missing_feature
            manifest_content = textwrap.dedent(
                f"""\
                ---
                manifest:
                  {FILENAME}::Test_SlowManifestMock: missing_feature (declared via manifest)
                """
            )
            manifest_file.write_text(manifest_content)

            # Run the test and verify it's skipped due to @slow + manifest declaration
            tests = run_system_tests(test_path=FILENAME)

            nodeid = f"{FILENAME}::Test_SlowManifestMock::test_slow_with_manifest"
            assert tests[nodeid]["outcome"] == "skipped"

        finally:
            # Restore original manifest
            shutil.move(backup_file, manifest_file)


@scenarios.test_the_test
class Test_SlowDecoratorOnClass:
    """Test that the @slow decorator works when applied to a class."""

    def test_slow_on_class_with_declaration_is_skipped(self):
        """Test that @slow on class combined with a declaration skips the test."""
        tests = run_system_tests(test_path=FILENAME)

        nodeid = f"{FILENAME}::Test_SlowOnClassMock::test_method"
        assert tests[nodeid]["outcome"] == "skipped"

    def test_slow_on_class_with_manifest_declaration_on_function_is_skipped(self):
        """Test that @slow on class with manifest declaration on function results in skip."""
        manifest_file = Path("manifests/java.yml")
        backup_file = Path("manifests/java.yml.backup")

        # Move original manifest to backup
        shutil.move(manifest_file, backup_file)

        try:
            # Create a manifest that declares the function (not the class) as missing_feature
            manifest_content = textwrap.dedent(
                f"""\
                ---
                manifest:
                  {FILENAME}::Test_SlowOnClassManifestMock::test_method: missing_feature (declared via manifest)
                """
            )
            manifest_file.write_text(manifest_content)

            # Run the test and verify it's skipped due to @slow on class + manifest declaration on function
            tests = run_system_tests(test_path=FILENAME)

            nodeid = f"{FILENAME}::Test_SlowOnClassManifestMock::test_method"
            assert tests[nodeid]["outcome"] == "skipped"

        finally:
            # Restore original manifest
            shutil.move(backup_file, manifest_file)


@scenarios.test_the_test
class Test_ScenarioCrashDecorator:
    """Test that the @scenario_crash decorator skips tests only when combined with a declaration."""

    def test_scenario_crash_alone_runs_normally(self):
        """Test that @scenario_crash alone does not skip the test."""
        tests = run_system_tests(test_path=FILENAME)

        nodeid = f"{FILENAME}::Test_ScenarioCrashMock::test_scenario_crash_alone"
        assert tests[nodeid]["outcome"] == "passed"

    def test_scenario_crash_with_declaration_is_skipped(self):
        """Test that @scenario_crash combined with a declaration skips the test."""
        tests = run_system_tests(test_path=FILENAME)

        nodeid = f"{FILENAME}::Test_ScenarioCrashMock::test_scenario_crash_with_missing_feature"
        assert tests[nodeid]["outcome"] == "skipped"


@scenarios.test_the_test
class Test_ScenarioCrashDecoratorOnClass:
    """Test that the @scenario_crash decorator works when applied to a class."""

    def test_scenario_crash_on_class_with_declaration_is_skipped(self):
        """Test that @scenario_crash on class combined with a declaration skips the test."""
        tests = run_system_tests(test_path=FILENAME)

        nodeid = f"{FILENAME}::Test_ScenarioCrashOnClassMock::test_method"
        assert tests[nodeid]["outcome"] == "skipped"


@scenarios.test_the_test
class Test_SkipIfXfail:
    """Test that tests with both skip_if_xfail and declaration markers are skipped."""

    def test_skip_if_xfail_with_declaration_is_skipped(self):
        """Test that a test marked with both skip_if_xfail and a declaration marker is skipped."""
        tests = run_system_tests(test_path=FILENAME)

        nodeid = f"{FILENAME}::Test_SkipIfXfailMock::test_with_both_markers"
        assert tests[nodeid]["outcome"] == "skipped"

    def test_skip_if_xfail_without_declaration_is_not_skipped(self):
        """Test that a test marked with only skip_if_xfail (no declaration) is not skipped."""
        tests = run_system_tests(test_path=FILENAME)

        nodeid = f"{FILENAME}::Test_SkipIfXfailMock::test_skip_if_xfail_only"
        assert tests[nodeid]["outcome"] == "passed"


# Mock test classes used by the test scenarios above


@scenarios.mock_the_test
@features.adaptive_sampling
class Test_SlowMock:
    @slow
    def test_slow_alone(self):
        """Test with only @slow - should run normally."""
        assert True

    @slow
    @bug(condition=True, reason="FAKE-001")
    def test_slow_with_bug(self):
        """Test with @slow and @bug() - should be skipped."""
        assert True


@scenarios.mock_the_test
@features.adaptive_sampling
class Test_ScenarioCrashMock:
    @scenario_crash
    def test_scenario_crash_alone(self):
        """Test with only @scenario_crash - should run normally."""
        assert True

    @scenario_crash
    @missing_feature(condition=True)
    def test_scenario_crash_with_missing_feature(self):
        """Test with @scenario_crash and @missing_feature() - should be skipped."""
        assert True


@scenarios.mock_the_test
@features.adaptive_sampling
class Test_SkipIfXfailMock:
    @bug(condition=True, reason="FAKE-001")
    @pytest.mark.skip_if_xfail
    def test_with_both_markers(self):
        """Test with both skip_if_xfail and declaration markers - should be skipped."""
        assert True

    @pytest.mark.skip_if_xfail
    def test_skip_if_xfail_only(self):
        """Test with only skip_if_xfail marker, no declaration - should NOT be skipped."""
        assert True


@scenarios.mock_the_test
@features.adaptive_sampling
class Test_SlowManifestMock:
    @slow
    def test_slow_with_manifest(self):
        """Test with @slow and manifest declaration - should be skipped."""
        assert True


@slow
@bug(condition=True, reason="FAKE-001")
@scenarios.mock_the_test
@features.adaptive_sampling
class Test_SlowOnClassMock:
    def test_method(self):
        """Test in class with @slow and @bug() on class - should be skipped."""
        assert True


@slow
@scenarios.mock_the_test
@features.adaptive_sampling
class Test_SlowOnClassManifestMock:
    def test_method(self):
        """Test in class with @slow on class and manifest declaration on function - should be skipped."""
        assert True


@scenario_crash
@missing_feature(condition=True)
@scenarios.mock_the_test
@features.adaptive_sampling
class Test_ScenarioCrashOnClassMock:
    def test_method(self):
        """Test in class with @scenario_crash and @missing_feature() on class - should be skipped."""
        assert True
