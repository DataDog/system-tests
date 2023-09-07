import pytest
from utils.tools import logger
import os
import json

from utils import missing_feature, irrelevant, released, coverage, scenarios, rfc


@scenarios.test_the_test
class Test_Json_Report:
    @classmethod
    def setup_class(cls):
        stream = os.popen("./run.sh MOCK_THE_TEST")
        output = stream.read()
        logger.info(output)

        f = open("logs_mock_the_test/report.json")
        cls.report_json = json.load(f)
        f.close()

    def test_missing_feature(self):
        """Report is generated with correct outcome and skip reason nodes for missing features decorators"""

        for test in self.report_json["tests"]:
            if test["nodeid"] == "tests/test_the_test/test_json_report.py::Test_Mock::test_missing_feature":
                assert test["outcome"] == "xfailed"
                assert test["skip_reason"] == "missing_feature: missing feature"
                return
        pytest.fail("Test method not found")

    def test_irrelevant(self):
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
            assert len(test) == 3  # nodeid, outcome and skip_reason

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
            == "0.0.99"
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


@scenarios.mock_the_test
@released(java="0.0.99")
@rfc("https://mock")
@coverage.good
class Test_Mock:
    def test_mock(self):
        """Mock test doc"""
        assert 1 == 1

    @missing_feature(True, reason="missing feature")
    def test_missing_feature(self):
        raise Exception("Should not be executed")

    @irrelevant(True, reason="irrelevant")
    def test_irrelevant(self):
        raise Exception("Should not be executed")
