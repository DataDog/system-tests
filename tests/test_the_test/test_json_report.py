import os
import json
import pytest
from utils.tools import logger

from utils import missing_feature, irrelevant, coverage, scenarios, rfc, features, bug, flaky

pytestmark = pytest.mark.features(feature_id=666)


BASE_PATH = "tests/test_the_test/test_json_report.py"


@scenarios.test_the_test
class Test_Json_Report:
    @classmethod
    def setup_class(cls):
        stream = os.popen("./run.sh MOCK_THE_TEST")
        output = stream.read()

        logger.info(output)

        with open("logs_mock_the_test/report.json", encoding="utf-8") as f:
            cls.report_json = json.load(f)

        with open("logs_mock_the_test/feature_parity.json", encoding="utf-8") as f:
            cls.feature_parity_report = json.load(f)

        with open("logs_mock_the_test/tests.log", encoding="utf-8") as f:
            cls.logs = [line.split(" ", 1)[1] for line in f.readlines()]

    def get_test(self, nodeid):
        for test in self.report_json["tests"]:
            if test["nodeid"] == nodeid:
                return test

        raise ValueError(f"Test not found: {nodeid}")

    def get_test_fp(self, nodeid):
        for test in self.feature_parity_report["tests"]:
            if test["path"] == f"tests/test_the_test/test_json_report.py::{nodeid}":
                return test

        raise ValueError(f"Test not found: {nodeid}")

    def test_missing_feature(self):
        """Report is generated with correct outcome and skip reason nodes for missing features decorators"""

        test = self.get_test("tests/test_the_test/test_json_report.py::Test_Mock::test_missing_feature")

        assert test["outcome"] == "xfailed"
        assert test["skip_reason"] == "missing_feature: not yet done"

    def test_irrelevant_legacy(self):
        """Report is generated with correct outcome and skip reason nodes for irrelevant decorators"""

        for test in self.report_json["tests"]:
            if test["nodeid"] == "tests/test_the_test/test_json_report.py::Test_Mock::test_irrelevant":
                assert test["outcome"] == "skipped"
                assert test["skip_reason"] == "irrelevant: irrelevant"
                return
        pytest.fail("Test method not found")

    def test_pass(self):
        """Report is generated with correct test data when a test is passed"""

        for test in self.report_json["tests"]:
            if test["nodeid"] == "tests/test_the_test/test_json_report.py::Test_Mock::test_mock":
                assert test["outcome"] == "passed"
                assert test["skip_reason"] is None
                return
        pytest.fail("Test method not found")

    def test_clean_test_data(self):
        """We are no adding more information that we need for each test"""

        for test in self.report_json["tests"]:
            assert len(test) == 5  # nodeid, lineno, outcome, metadata and skip_reason

    def test_docs(self):
        """Docs node is generating"""

        assert "tests/test_the_test/test_json_report.py::Test_Mock::test_mock" in self.report_json["docs"]
        assert (
            self.report_json["docs"]["tests/test_the_test/test_json_report.py::Test_Mock::test_mock"] == "Mock test doc"
        )

    def test_rfcs(self):
        """Rfcs node is generating"""

        assert "tests/test_the_test/test_json_report.py::Test_Mock" in self.report_json["rfcs"]
        assert self.report_json["rfcs"]["tests/test_the_test/test_json_report.py::Test_Mock"] == "https://mock"

    def test_coverages(self):
        """coverages node is generating"""

        assert "tests/test_the_test/test_json_report.py::Test_Mock" in self.report_json["coverages"]
        assert self.report_json["coverages"]["tests/test_the_test/test_json_report.py::Test_Mock"] == "good"

    def test_release_versions(self):
        """release_versions node is generating"""

        assert "tests/test_the_test/test_json_report.py::Test_Mock" in self.report_json["release_versions"]
        assert "java" in self.report_json["release_versions"]["tests/test_the_test/test_json_report.py::Test_Mock"]
        assert (
            self.report_json["release_versions"]["tests/test_the_test/test_json_report.py::Test_Mock"]["java"]
            == "v0.0.99"
        )

    def test_context_serialization(self):
        """check context serialization node is generating"""

        assert "context" in self.report_json
        # Check agent node (version is set on TestTheTest scenario)
        assert "agent" in self.report_json["context"]
        assert self.report_json["context"]["agent"] == "0.77.0"
        # Check library node (version is set on TestTheTest scenario)
        assert "library" in self.report_json["context"]
        assert "library" in self.report_json["context"]["library"]
        assert self.report_json["context"]["library"]["library"] == "java"
        assert "version" in self.report_json["context"]["library"]
        assert self.report_json["context"]["library"]["version"] == "0.66.0"
        # Check weblog node (version is set on TestTheTest scenario)
        assert "weblog_variant" in self.report_json["context"]
        assert self.report_json["context"]["weblog_variant"] == "spring"
        # Check custom components ( set on TestTheTest scenario)
        assert "mock_comp1" in self.report_json["context"]
        assert self.report_json["context"]["mock_comp1"] == "mock_comp1_value"
        # Check parametrized_tests_metadata ( set on TestTheTest scenario)
        assert "parametrized_tests_metadata" in self.report_json["context"]
        assert (
            "tests/test_the_test/test_json_report.py::Test_Mock::test_mock"
            in self.report_json["context"]["parametrized_tests_metadata"]
        )
        assert (
            "meta1"
            in self.report_json["context"]["parametrized_tests_metadata"][
                "tests/test_the_test/test_json_report.py::Test_Mock::test_mock"
            ]
        )

    def test_feature_id(self):
        test = self.get_test("tests/test_the_test/test_json_report.py::Test_Mock::test_mock")
        assert test["metadata"]["features"] == [13, 74, 666]

        test = self.get_test("tests/test_the_test/test_json_report.py::Test_Mock::test_missing_feature")
        assert test["metadata"]["features"] == [75, 13, 74, 666]

    def test_skip_reason(self):
        """the skip reason must be the closest to the test method"""
        test = self.get_test("tests/test_the_test/test_json_report.py::Test_Mock2::test_skipped")
        assert test["metadata"]["skip_reason"] == "bug: local reason"

    def test_xpassed(self):
        test = self.get_test_fp("Test_BugClass::test_xpassed_method")
        assert test["outcome"] == "xpassed"

        test = self.get_test_fp("Test_BugClass::test_xfailed_method")
        assert test["outcome"] == "xfailed"

    def test_released_manifest(self):
        test = self.get_test_fp("Test_NotReleased::test_method")
        assert test["outcome"] == "xpassed"
        assert test["testDeclaration"] == "notImplemented"

    def test_irrelevant(self):
        test = self.get_test_fp("Test_IrrelevantClass::test_method")
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
@coverage.good
@features.api_v2_implemented
@features.b3_headers_injection_and_extraction
class Test_Mock:
    def test_mock(self):
        """Mock test doc"""
        assert 1 == 1

    @missing_feature(True, reason="not yet done")
    @features.app_client_configuration_change_event
    def test_missing_feature(self):
        raise ValueError("Should not be executed")

    @irrelevant(True, reason="irrelevant")
    def test_irrelevant(self):
        raise ValueError("Should not be executed")


@scenarios.mock_the_test
@bug(True, reason="global reason")
class Test_Mock2:
    @bug(True, reason="local reason")
    def test_skipped(self):
        raise ValueError("Should not be executed")


@scenarios.mock_the_test
@bug(True)
class Test_BugClass:
    def test_xpassed_method(self):
        """This test will be reported as xpassed"""
        assert True

    def test_xfailed_method(self):
        """This test will be reported as xpassed"""
        assert False


@scenarios.mock_the_test
class Test_NotReleased:
    def test_method(self):
        assert True


@irrelevant(True)
@scenarios.mock_the_test
class Test_IrrelevantClass:
    def test_method(self):
        raise ValueError("Should not be executed")


@scenarios.mock_the_test
class Test_Class:
    @irrelevant(True)
    def test_irrelevant_method(self):
        raise ValueError("Should not be executed")

    @flaky(True)
    def test_flaky_method(self):
        raise ValueError("Should not be executed")

    @irrelevant(condition=False)
    @flaky(condition=False)
    def test_good_method(self):
        pass

    @missing_feature(True, reason="not yet done")
    @irrelevant(True, reason="irrelevant")
    def test_skipping_prio(self):
        raise ValueError("Should not be executed")

    @irrelevant(True, reason="irrelevant")
    @missing_feature(True, reason="not yet done")
    def test_skipping_prio2(self):
        raise ValueError("Should not be executed")


@flaky(True)
@scenarios.mock_the_test
class Test_FlakyClass:
    def test_method(self):
        raise Exception("Should not be executed")
