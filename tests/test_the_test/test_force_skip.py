from utils import bug, missing_feature, scenarios, features

from .utils import run_system_tests

FILENAME = "tests/test_the_test/test_force_skip.py"


@scenarios.test_the_test
class Test_ForceSkip:
    def test_force_bug(self):
        tests = run_system_tests(test_path=FILENAME)

        nodeid = f"{FILENAME}::Test_Bug::test_bug_executed"
        assert tests[nodeid]["outcome"] == "xpassed"

        nodeid = f"{FILENAME}::Test_Bug::test_missing_feature_executed"
        assert tests[nodeid]["outcome"] == "xpassed"

        nodeid = f"{FILENAME}::Test_Bug::test_bug_not_executed"
        assert tests[nodeid]["outcome"] == "skipped"

        nodeid = f"{FILENAME}::Test_Bug::test_missing_feature_not_executed"
        assert tests[nodeid]["outcome"] == "skipped"


@scenarios.mock_the_test
@features.adaptive_sampling
class Test_Bug:
    @bug(condition=True, reason="FAKE-001")
    def test_bug_executed(self):
        assert True

    @missing_feature(condition=True)
    def test_missing_feature_executed(self):
        assert True

    @bug(condition=True, reason="FAKE-001", force_skip=True)
    def test_bug_not_executed(self):
        assert True

    @missing_feature(condition=True, force_skip=True)
    def test_missing_feature_not_executed(self):
        assert True
