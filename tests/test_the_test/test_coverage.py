import pytest
from utils import coverage


pytestmark = pytest.mark.scenario("TEST_THE_TEST")


class Test_NotTestable:
    def test_main(self):
        @coverage.not_testable
        class Test_NotTestableSample:
            pass

        assert hasattr(Test_NotTestableSample, "__coverage__")
        assert hasattr(Test_NotTestableSample, "test_fake")
        assert Test_NotTestableSample.__coverage__ == "not-testable"


class Test_NotImplemented:
    def test_main(self):
        @coverage.not_implemented
        class Test_NotImplementedSample:
            pass

        assert hasattr(Test_NotImplementedSample, "__coverage__")
        assert hasattr(Test_NotImplementedSample, "test_fake")
        assert Test_NotImplementedSample.__coverage__ == "not-implemented"


@coverage.basic
class Test_BasicCoverage:
    def test_main(self):
        assert hasattr(Test_BasicCoverage, "__coverage__")
        assert Test_BasicCoverage.__coverage__ == "basic"


@coverage.good
class Test_GoodCoverage:
    def test_main(self):
        assert hasattr(Test_GoodCoverage, "__coverage__")
        assert Test_GoodCoverage.__coverage__ == "good"


@coverage.complete
class Test_CompleteCoverage:
    def test_main(self):
        assert hasattr(Test_CompleteCoverage, "__coverage__")
        assert Test_CompleteCoverage.__coverage__ == "complete"


class Test_Errors:
    def test_duplicated(self):
        message = "coverage has been declared twice for <class 'tests.test_the_test.test_coverage.Test_Errors.test_duplicated.<locals>.Test'>"
        try:

            @coverage.basic
            @coverage.good
            class Test:
                pass

        except AssertionError as e:
            assert str(e) == message
        else:
            raise Exception("Declaring twice a covrage should raise an exception")
