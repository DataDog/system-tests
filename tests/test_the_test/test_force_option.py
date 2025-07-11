from utils import bug, irrelevant, scenarios

from .utils import run_system_tests

FILENAME = "tests/test_the_test/test_force_option.py"


def execute_process(forced_test):
    return run_system_tests(test_path=FILENAME, forced_test=forced_test)


@scenarios.test_the_test
class Test_ForceOption:
    def test_force_bug(self):
        nodeid = f"{FILENAME}::Test_Direct::test_bug"
        tests = execute_process(nodeid)

        assert tests[nodeid]["outcome"] == "passed"

    def test_force_irrelevant(self):
        nodeid = f"{FILENAME}::Test_Direct::test_irrelevant"
        tests = execute_process(nodeid)

        assert tests[nodeid]["outcome"] == "passed"

    def test_force_bug_nested(self):
        nodeid = f"{FILENAME}::Test_Bug::test_forced"
        tests = execute_process(nodeid)

        assert tests[f"{FILENAME}::Test_Bug::test_not_executed"]["outcome"] == "xpassed"
        assert tests[nodeid]["outcome"] == "passed", "The test should be forced, so not xpassed"

    def test_force_irrelevant_nested(self):
        nodeid = f"{FILENAME}::Test_Irrelevant::test_forced"
        tests = execute_process(nodeid)

        assert tests[f"{FILENAME}::Test_Irrelevant::test_not_executed"]["outcome"] == "skipped"
        assert tests[nodeid]["outcome"] == "passed", "The test should be forced, so not xpassed"


@bug(condition=True, reason="FAKE-001")
@scenarios.mock_the_test
class Test_Bug:
    def test_forced(self):
        assert True

    def test_not_executed(self):
        assert True


@irrelevant(condition=True)
@scenarios.mock_the_test
class Test_Irrelevant:
    def test_forced(self):
        assert True

    def test_not_executed(self):
        assert True


@scenarios.mock_the_test
class Test_Direct:
    @bug(condition=True, reason="FAKE-001")
    def test_bug(self):
        assert True

    @irrelevant(condition=True)
    def test_irrelevant(self):
        assert True
