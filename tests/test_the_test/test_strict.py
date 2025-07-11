from utils import bug, missing_feature, scenarios

from .utils import run_system_tests

FILENAME = "tests/test_the_test/test_strict.py"


@scenarios.test_the_test
class Test_StrictMode:
    def test_strict_missing_features(self):
        tests = run_system_tests(test_path=FILENAME, xfail_strict=True)

        assert tests[f"{FILENAME}::test_strict_bug"]["outcome"] == "failed"
        assert tests[f"{FILENAME}::test_strict_missing_feature"]["outcome"] == "failed"


@scenarios.mock_the_test
@bug(condition=True, reason="FAKE-001")
def test_strict_bug():
    assert True, "Bug fixed"


@scenarios.mock_the_test
@missing_feature(condition=True)
def test_strict_missing_feature():
    assert True, "I'm a feature implemented"
