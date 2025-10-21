import pytest

from utils import bug, irrelevant, scenarios, features
from utils._context._scenarios import Scenario

from .utils import run_system_tests

FILENAME = "tests/test_the_test/test_force_option.py"


def execute_process(
    scenario: Scenario = scenarios.mock_the_test, forced_test: str | None = None, env: dict[str, str] | None = None
):
    return run_system_tests(scenario=scenario.name, test_path=FILENAME, forced_test=forced_test, env=env)


@scenarios.test_the_test
@features.adaptive_sampling
class Test_ForceOption:
    def test_force_bug(self):
        nodeid = f"{FILENAME}::Test_Direct::test_bug"
        tests = execute_process(forced_test=nodeid)

        assert nodeid in tests
        assert tests[nodeid]["outcome"] == "passed"

    def test_force_irrelevant(self):
        nodeid = f"{FILENAME}::Test_Direct::test_irrelevant"
        tests = execute_process(forced_test=nodeid)

        assert tests[nodeid]["outcome"] == "passed"

    def test_force_bug_nested(self):
        nodeid = f"{FILENAME}::Test_Bug::test_forced"
        tests = execute_process(forced_test=nodeid)

        assert tests[f"{FILENAME}::Test_Bug::test_not_executed"]["outcome"] == "xpassed"
        assert tests[nodeid]["outcome"] == "passed", "The test should be forced, so not xpassed"

    def test_force_irrelevant_nested(self):
        nodeid = f"{FILENAME}::Test_Irrelevant::test_forced"
        tests = execute_process(forced_test=nodeid)

        assert tests[f"{FILENAME}::Test_Irrelevant::test_not_executed"]["outcome"] == "skipped"
        assert tests[nodeid]["outcome"] == "passed", "The test should be forced, so not xpassed"

    def test_force_in_another_scenario(self):
        nodeid = f"{FILENAME}::Test_Another::test_main"

        tests = execute_process(forced_test=nodeid)
        assert nodeid not in tests

        tests = execute_process(scenario=scenarios.mock_the_test_2, forced_test=nodeid)
        assert nodeid in tests
        assert tests[nodeid]["outcome"] == "passed"  # force to execute

    def test_with_env(self):
        nodeid_forced = f"{FILENAME}::Test_Another::test_main"
        nodeid_skipped = f"{FILENAME}::Test_Another::test_skipped"

        env = {"SYSTEM_TESTS_FORCE_EXECUTE": f"{nodeid_forced},<other_nodeid>"}

        tests = execute_process(scenario=scenarios.mock_the_test_2, env=env)
        assert nodeid_forced in tests
        assert nodeid_skipped in tests

        assert tests[nodeid_forced]["outcome"] == "passed"  # force to execute
        assert tests[nodeid_skipped]["outcome"] == "xfailed"


@bug(condition=True, reason="FAKE-001")
@scenarios.mock_the_test
@features.adaptive_sampling
class Test_Bug:
    def test_forced(self):
        assert True

    def test_not_executed(self):
        assert True


@irrelevant(condition=True)
@scenarios.mock_the_test
@features.adaptive_sampling
class Test_Irrelevant:
    def test_forced(self):
        assert True

    def test_not_executed(self):
        assert True


@scenarios.mock_the_test
@features.adaptive_sampling
class Test_Direct:
    @bug(condition=True, reason="FAKE-001")
    def test_bug(self):
        assert True

    @irrelevant(condition=True)
    def test_irrelevant(self):
        assert True


@scenarios.mock_the_test_2
@features.adaptive_sampling
class Test_Another:
    @bug(condition=True, reason="FAKE-001")
    def test_main(self):
        assert True

    @bug(condition=True, reason="FAKE-001")
    def test_skipped(self):
        pytest.fail("Expected failure")
