import os
from utils import pytest

from utils import missing_feature, irrelevant, scenarios, rfc, features, bug, flaky, logger

from .utils import read_junit_report, read_junit_suite_properties

pytestmark = pytest.mark.features(feature_id=666)


BASE_PATH = "tests/test_the_test/test_junit_report.py"


@scenarios.test_the_test
class Test_Junit_Report:
    logs: list[str]
    report: dict[str, dict]
    suite_properties: dict[str, str]

    @classmethod
    def setup_class(cls) -> None:
        stream = os.popen("./run.sh MOCK_THE_TEST")
        output = stream.read()

        logger.info(output)

        cls.report = read_junit_report("MOCK_THE_TEST")
        cls.suite_properties = read_junit_suite_properties("MOCK_THE_TEST")

        with open("logs_mock_the_test/tests.log", encoding="utf-8") as f:
            cls.logs = [line.split(" ", 1)[1] for line in f]

    def get_test(self, nodeid: str) -> dict:
        return self.report[f"{BASE_PATH}::{nodeid}"]

    def assert_irrelevant(self, nodeid: str) -> None:
        """Irrelevant tests are skipped, and removed from the junit report"""
        assert f"DEBUG    {BASE_PATH}::{nodeid} => irrelevant => skipped\n" in self.logs
        assert f"{BASE_PATH}::{nodeid}" not in self.report

    def test_missing_feature(self):
        """Report is generated with correct outcome and skip reason nodes for missing features decorators"""
        test = self.get_test("Test_Mock::test_missing_feature")

        assert test["outcome"] == "xfailed"
        assert test["declaration"] == "missing_feature", test
        assert test["declaration_details"] == "not yet done", test

    def test_irrelevant_legacy(self):
        """Irrelevant decorators on methods remove the test from the report"""
        self.assert_irrelevant("Test_Mock::test_irrelevant")

    def test_pass(self):
        """Report is generated with correct test data when a test is passed"""
        test = self.get_test("Test_Mock::test_mock")
        assert test["outcome"] == "passed"
        assert test["declaration"] is None
        assert test["declaration_details"] is None

    def test_clean_test_data(self):
        """We are not adding more information than we need for each test"""
        allowed = {
            "test.codeowners",
            "dd_tags[systest.case.feature_ids]",
            "dd_tags[systest.case.declaration]",
            "dd_tags[systest.case.declarationDetails]",
            "dd_tags[systest.case.outcome]",
            "dd_tags[test.final_status]",
        }
        for nodeid, test in self.report.items():
            assert set(test["properties"]) <= allowed, (nodeid, list(test["properties"]))

    def test_context_serialization(self):
        """Check that the context is exported as junit properties of the suite"""
        assert self.suite_properties["dd_tags[systest.suite.context.scenario]"] == "MOCK_THE_TEST"
        assert self.suite_properties["dd_tags[test.parameters]"] == '{"scenario": "MOCK_THE_TEST"}'

    def test_feature_id(self):
        test = self.get_test("Test_Mock::test_mock")
        assert test["features"] == [13, 74, 666]

        test = self.get_test("Test_Mock::test_missing_feature")
        assert test["features"] == [75, 13, 74, 666]

    def test_skip_reason(self):
        """The skip reason must be the closest to the test method"""
        test = self.get_test("Test_Mock2::test_skipped")
        assert test["declaration"] == "bug"
        assert test["declaration_details"] == "FAKE-002"

    def test_xpassed(self):
        test = self.get_test("Test_BugClass::test_xpassed_method")
        assert test["outcome"] == "xpassed"

        test = self.get_test("Test_BugClass::test_xfailed_method")
        assert test["outcome"] == "xfailed"

    def test_released_manifest(self):
        test = self.get_test("Test_NotReleased::test_method")
        assert test["outcome"] == "xpassed"
        assert test["declaration"] == "missing_feature"

    def test_irrelevant(self):
        self.assert_irrelevant("Test_IrrelevantClass::test_method")

    def test_flaky_in_irrelevant(self):
        self.assert_irrelevant("Test_IrrelevantClass::test_flaky_method_in_irrelevant_class")

    def test_bug_in_irrelevant(self):
        self.assert_irrelevant("Test_IrrelevantClass::test_bug_method_in_irrelevant_class")

    def test_doubleskip(self):
        """Irrelevant has priority over missing_feature, whatever the decorator order"""
        self.assert_irrelevant("Test_Class::test_skipping_prio")
        self.assert_irrelevant("Test_Class::test_skipping_prio2")

    def test_flaky(self):
        test = self.get_test("Test_Class::test_flaky_method")
        assert test["outcome"] == "skipped"
        assert test["declaration"] == "flaky"

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
