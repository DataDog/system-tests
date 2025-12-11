import os
import json
import pytest

from utils import missing_feature, irrelevant, scenarios, rfc, features, bug, flaky, logger

pytestmark = pytest.mark.features(feature_id=666)


BASE_PATH = "tests/test_the_test/test_json_report.py"


@scenarios.test_the_test
class Test_Json_Report:
    logs: list[str]
    report: dict

    @classmethod
    def setup_class(cls) -> None:
        stream = os.popen("./run.sh MOCK_THE_TEST")
        output = stream.read()

        logger.info(output)

        with open("logs_mock_the_test/feature_parity.json", encoding="utf-8") as f:
            cls.report = json.load(f)

        with open("logs_mock_the_test/tests.log", encoding="utf-8") as f:
            cls.logs = [line.split(" ", 1)[1] for line in f]

    def get_test_fp(self, nodeid: str):
        for test in self.report["tests"]:
            if test["path"] == f"tests/test_the_test/test_json_report.py::{nodeid}":
                return test

        raise ValueError(f"Test not found: {nodeid}")

    def test_missing_feature(self):
        """Report is generated with correct outcome and skip reason nodes for missing features decorators"""
        test = self.get_test_fp("Test_Mock::test_missing_feature")

        assert test["outcome"] == "xfailed"
        assert test["details"] == "missing_feature (not yet done)", test

    def test_irrelevant_legacy(self):
        """Report is generated with correct outcome and skip reason nodes for irrelevant decorators"""
        test = self.get_test_fp("Test_Mock::test_irrelevant")

        assert test["outcome"] == "skipped"
        assert test["details"] == "irrelevant (never be done)", test

    def test_pass(self):
        """Report is generated with correct test data when a test is passed"""
        test = self.get_test_fp("Test_Mock::test_mock")
        assert test["outcome"] == "passed"
        assert test["details"] is None

    def test_clean_test_data(self):
        """We are no adding more information that we need for each test"""

        for test in self.report["tests"]:
            assert len(test) == 6, list(test.keys())  # testDeclaration, details, features, outcome, lineNumber and path

    def test_context_serialization(self):
        """Check context serialization node is generating"""

        # Check library node (version is set on TestTheTest scenario)
        assert self.report["language"] == "java", list(self.report)

        # Check weblog node (version is set on TestTheTest scenario)
        assert self.report["variant"] == "spring"

        # Check custom components ( set on TestTheTest scenario)
        assert "testedDependencies" in self.report
        assert self.report["testedDependencies"][0]["name"] == "mock_comp1"
        assert self.report["testedDependencies"][0]["version"] == "mock_comp1_value"

    def test_feature_id(self):
        test = self.get_test_fp("Test_Mock::test_mock")
        assert test["features"] == [13, 74, 666]

        test = self.get_test_fp("Test_Mock::test_missing_feature")
        assert test["features"] == [75, 13, 74, 666]

    def test_skip_reason(self):
        """The skip reason must be the closest to the test method"""
        test = self.get_test_fp("Test_Mock2::test_skipped")
        assert test["testDeclaration"] == "bug"
        assert test["details"] == "bug (FAKE-002)"

    def test_xpassed(self):
        test = self.get_test_fp("Test_BugClass::test_xpassed_method")
        assert test["outcome"] == "xpassed"

        test = self.get_test_fp("Test_BugClass::test_xfailed_method")
        assert test["outcome"] == "xfailed"

    def test_released_manifest(self):
        test = self.get_test_fp("Test_NotReleased::test_method")
        assert test["outcome"] == "xpassed"
        assert test["testDeclaration"] == "missing_feature"

    def test_irrelevant(self):
        test = self.get_test_fp("Test_IrrelevantClass::test_method")
        assert test["outcome"] == "skipped"
        assert test["testDeclaration"] == "irrelevant"

    def test_flaky_in_irrelevant(self):
        test = self.get_test_fp("Test_IrrelevantClass::test_flaky_method_in_irrelevant_class")
        assert test["outcome"] == "skipped"
        assert test["testDeclaration"] == "irrelevant"

    def test_bug_in_irrelevant(self):
        test = self.get_test_fp("Test_IrrelevantClass::test_bug_method_in_irrelevant_class")
        assert test["outcome"] == "skipped"
        assert test["testDeclaration"] == "irrelevant"

    def test_doubleskip(self):
        test = self.get_test_fp("Test_Class::test_skipping_prio")
        assert test["outcome"] == "skipped"
        assert test["testDeclaration"] == "irrelevant"

        test = self.get_test_fp("Test_Class::test_skipping_prio2")
        assert test["outcome"] == "skipped"
        assert test["testDeclaration"] == "irrelevant"

    def test_flaky(self):
        test = self.get_test_fp("Test_Class::test_flaky_method")
        assert test["outcome"] == "skipped"
        assert test["testDeclaration"] == "flaky"

    def test_logs(self):
        assert f"DEBUG    {BASE_PATH}::Test_IrrelevantClass::test_method => irrelevant => skipped\n" in self.logs
        assert f"DEBUG    {BASE_PATH}::Test_Class::test_irrelevant_method => irrelevant => skipped\n" in self.logs
        assert f"DEBUG    {BASE_PATH}::Test_FlakyClass::test_method => flaky => skipped\n" in self.logs
        assert f"DEBUG    {BASE_PATH}::Test_Class::test_flaky_method => flaky => skipped\n" in self.logs


@scenarios.mock_the_test
@rfc("https://mock")
@features.telemetry_api_v2_implemented
@features.b3_headers_propagation
class Test_Mock:
    def test_mock(self):
        """Mock test doc"""
        assert 1 == 1  # noqa: PLR0133

    @missing_feature(condition=True, reason="not yet done")
    @features.app_client_configuration_change_event
    def test_missing_feature(self):
        raise ValueError("Should not be executed")

    @irrelevant(condition=True, reason="never be done")
    def test_irrelevant(self):
        raise ValueError("Should not be executed")


@scenarios.mock_the_test
@bug(condition=True, reason="FAKE-001")
class Test_Mock2:
    @bug(condition=True, reason="FAKE-002")
    def test_skipped(self):
        raise ValueError("Should not be executed")


@scenarios.mock_the_test
@bug(condition=True, reason="FAKE-001")
class Test_BugClass:
    def test_xpassed_method(self):
        """This test will be reported as xpassed"""
        assert True

    def test_xfailed_method(self):
        """This test will be reported as xpassed"""
        pytest.fail("Expected")


@scenarios.mock_the_test
class Test_NotReleased:
    def test_method(self):
        assert True


@irrelevant(condition=True)
@scenarios.mock_the_test
class Test_IrrelevantClass:
    def test_method(self):
        raise ValueError("Should not be executed")

    @flaky(condition=True, reason="FAKE-001")
    def test_flaky_method_in_irrelevant_class(self):
        raise ValueError("Should not be executed")

    @bug(condition=True, reason="FAKE-001")
    def test_bug_method_in_irrelevant_class(self):
        raise ValueError("Should not be executed")


@scenarios.mock_the_test
class Test_Class:
    @irrelevant(condition=True)
    def test_irrelevant_method(self):
        raise ValueError("Should not be executed")

    @flaky(condition=True, reason="FAKE-001")
    def test_flaky_method(self):
        raise ValueError("Should not be executed")

    @irrelevant(condition=False)
    @flaky(condition=False, reason="FAKE-001")
    def test_good_method(self):
        pass

    @missing_feature(condition=True, reason="not yet done")
    @irrelevant(condition=True, reason="never be done")
    def test_skipping_prio(self):
        raise ValueError("Should not be executed")

    @irrelevant(condition=True, reason="never be done")
    @missing_feature(condition=True, reason="not yet done")
    def test_skipping_prio2(self):
        raise ValueError("Should not be executed")


@flaky(condition=True, reason="FAKE-001")
@scenarios.mock_the_test
class Test_FlakyClass:
    def test_method(self):
        raise Exception("Should not be executed")
