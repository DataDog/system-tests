import sys
import pytest
import logging
from utils import interfaces, bug, context, irrelevant, missing_feature
from utils.tools import logger
from utils._context.library_version import LibraryVersion


# monkey patch
context.execute_warmups = lambda *args, **kwargs: None


class Logs(list):
    def write(self, line):
        self.append(line)

    def __str__(self):
        return "\n".join([l.strip() for l in self])


@pytest.fixture()
def logs():
    logs = Logs()
    handler = logging.StreamHandler(stream=logs)
    logger.addHandler(handler)
    yield logs
    logger.removeHandler(handler)


class Test_All:
    def test_decorators(self, logs):
        from utils._decorators import bug, released, rfc, irrelevant

        context.library = LibraryVersion("java", "0.66.0")

        def is_skipped(item, reason):
            if not hasattr(item, "pytestmark"):
                print(f"{item} has not pytestmark attribute")
            else:
                for mark in item.pytestmark:
                    if mark.name in ("skip", "expected_failure"):

                        if mark.kwargs["reason"] == reason:
                            print(f"Found expected {mark} for {item}")
                            return True

                        print(f"{item} is skipped, but reason is {repr(mark.kwargs['reason'])} io {repr(reason)}")

            raise Exception(f"{item} is not skipped, or not with the good reason")

        def is_not_skipped(item):
            if hasattr(item, "pytestmark"):
                for mark in item.pytestmark:
                    if mark.name == ("skip", "expected_failure"):
                        raise Exception(f"{item} is skipped")

            return True

        @bug(library="java", reason="test")
        def test_function():
            pass

        @bug(library="java", reason="test")
        class Test_Class:
            @irrelevant(library="java")
            def test_method(self):
                pass

            @irrelevant(library="nodejs")
            def test_method2(self):
                pass

            @missing_feature(True, reason="missing feature")
            @irrelevant(True, reason="irrelevant")
            def test_method3(self):
                pass

            @irrelevant(True, reason="irrelevant")
            @missing_feature(True, reason="missing feature")
            def test_method4(self):
                pass

        assert is_skipped(test_function, "known bug: test")
        assert "test_function => known bug: test => xfail\n" in logs
        assert is_skipped(Test_Class, "known bug: test")
        assert is_skipped(Test_Class.test_method, "not relevant")
        assert is_not_skipped(Test_Class.test_method2)
        assert "test_method => not relevant => skipped\n" in logs
        assert "Test_Class => known bug: test => xfail\n" in logs
        assert is_skipped(Test_Class.test_method3, "not relevant: irrelevant")
        assert is_skipped(Test_Class.test_method4, "not relevant: irrelevant")

        @rfc("A link")
        @released(java="99.99")
        @released(php="99.99")
        class Test2:
            pass

        assert (
            "Test2 class, missing feature for java: release version is 99.99, tested version is 0.66.0 => skipped\n"
            in logs
        )
        assert Test2().__released__["java"] == "99.99"
        assert "php" not in Test2().__released__
        assert Test2().__rfc__ == "A link"

        try:

            @released(java="99.99")
            @released(java="99.99")
            class Test3:
                pass

        except ValueError as e:
            assert str(e) == "A java' version for Test3 has been declared twice"
        else:
            raise Exception("Component has been declared twice, should fail")

        @released(java="?")
        class Test4:
            pass

        assert is_skipped(Test4, "missing feature: release not yet planned")

    def test_version_comparizon(self):
        from utils._context.library_version import Version

        v = Version("1.0", "some_component")

        assert v == "1.0"
        assert v != "1.1"

        assert v <= "1.1"
        assert v <= "1.0"
        assert "1.1" >= v
        assert "1.0" >= v

        assert v < "1.1"
        assert "1.1" > v

        assert v >= "0.9"
        assert v >= "1.0"
        assert "0.9" <= v
        assert "1.0" <= v

        assert v > "0.9"
        assert "0.9" < v

        assert Version("1.31.1", "") < "v1.34.1"
        assert "1.31.1" < Version("v1.34.1", "")
        assert Version("1.31.1", "") < Version("v1.34.1", "")

        assert Version("  * ddtrace (1.0.0.beta1)", "ruby") == Version("1.0.0.beta1", "ruby")
        assert Version("  * ddtrace (1.0.0.beta1)", "ruby")
        assert Version("  * ddtrace (1.0.0.beta1)", "ruby") < Version("  * ddtrace (1.0.0.beta1 de82857)", "ruby")
        assert Version("  * ddtrace (1.0.0.beta1 de82857)", "ruby") < Version("1.0.0", "ruby")

        assert Version("1.0.0beta1", "ruby") < Version("1.0.0beta1+8a50f1f", "ruby")

    def test_version_serialization(self):
        from utils._context.library_version import Version

        assert Version("v1.3.1", "cpp") == "1.3.1"
        assert str(Version("v1.3.1", "cpp")) == "1.3.1"

        v = Version("0.53.0.dev70+g494e6dc0", "some comp")
        assert v == "0.53.0.dev70+g494e6dc0"
        assert str(v) == "0.53.0.dev70+g494e6dc0"

        v = Version("  * ddtrace (0.53.0.appsec.180045)", "ruby")
        assert v == Version("0.53.0appsec.180045", "ruby")
        assert v == "0.53.0appsec.180045"

        v = Version("  * ddtrace (1.0.0.beta1)", "ruby")
        assert v == Version("1.0.0beta1", "ruby")

        v = Version("  * ddtrace (1.0.0.beta1 de82857)", "ruby")
        assert v == Version("1.0.0beta1+de82857", "ruby")

        v = Version("* libddwaf (1.0.14.1.0.beta1)", "libddwaf")
        assert v == Version("1.0.14.1.0.beta1", "libddwaf")
        assert v == "1.0.14.1.0.beta1"

        v = Version("Agent 7.33.0 - Commit: e6cfcb9 - Serialization version: v5.0.4 - Go version: go1.16.7", "agent")
        assert v == "7.33.0"

        v = Version("1.0.0-nightly", "php")
        assert v == "1.0.0"

        v = Version("3.0.0pre0", "nodejs")
        assert v == "3.0.0pre0"

    def test_library_version(self):
        from utils._context.library_version import LibraryVersion

        v = LibraryVersion("p")
        assert v == "p"
        assert v != "u"

        v = LibraryVersion("p", "1.0")

        assert v == "p@1.0"
        assert v == "p"
        assert v != "p@1.1"
        assert v != "u"

        assert v <= "p@1.1"
        assert v <= "p@1.0"
        assert "p@1.1" >= v
        assert "p@1.0" >= v

        assert v < "p@1.1"
        assert "p@1.1" > v

        assert v >= "p@0.9"
        assert v >= "p@1.0"
        assert "p@0.9" <= v
        assert "p@1.0" <= v

        assert v > "p@0.9"
        assert "p@0.9" < v

        assert (v <= "u@1.0") is False
        assert (v >= "u@1.0") is False

        assert ("u@1.0" <= v) is False
        assert ("u@1.0" >= v) is False

        v = LibraryVersion("p")

        assert ("u@1.0" == v) is False
        assert ("u@1.0" <= v) is False

        v = LibraryVersion("python", "0.53.0.dev70+g494e6dc0")
        assert v == "python@0.53.0.dev70+g494e6dc0"

        v = LibraryVersion("java", "0.94.1~dde6877139")
        assert v == "java@0.94.1"
        assert v >= "java@0.94.1"
        assert v < "java@0.94.2"

        v = LibraryVersion("java", "0.94.0-SNAPSHOT~57664cfbe5")
        assert v == "java@0.94.0"
        assert v >= "java@0.94.0"
        assert v < "java@0.94.1"

    def test_stdout_reader(self):
        """ Test stdout reader """

        from utils.interfaces._logs.core import _LibraryStdout

        with open("logs/docker/weblog/stdout.log", "w") as f:
            f.write("[dd.trace 2021-11-29 17:10:22:203 +0000] [main] DEBUG com.klass - some file\n")
            f.write("[dd.trace 2021-11-29 17:10:22:203 +0000] [main] INFO com.klass - AppSec initial 1.0.14\n")

        stdout = _LibraryStdout()

        stdout.assert_absence(r"System\.Exception")
        stdout.assert_presence(r"some.*file")
        stdout.assert_presence(r"AppSec initial \d+\.\d+\.\d+", level="INFO")

        stdout.assert_presence(r"some.*file", level="DEBUG")
        stdout.append_log_validation(lambda data: data["level"])

        stdout.wait()

        for v in stdout._validations:
            assert v.is_success, v

    def test_message_collector(self):
        """ Test magic message collector """
        from utils.interfaces._core import BaseValidation

        assert BaseValidation("Inline message").message == "Inline message"
        assert BaseValidation().message == "Test magic message collector", repr(BaseValidation().message)

        class Test_Class:
            """ A test class """

            def test_A(self):
                assert BaseValidation("Inline message").message == "Inline message"
                assert BaseValidation().message == "A test class"

            def test_B(self):
                """ A test method """
                assert BaseValidation("Inline message").message == "Inline message"
                assert BaseValidation().message == "A test method"

        Test_Class().test_A()
        Test_Class().test_B()

    @bug(True, reason="Can't succeed")
    def test_failing(self):
        """Failing test"""
        interfaces.library_stdout.assert_presence("nope i do not exists")
        interfaces.library_stdout.assert_absence("nope i do not exists")


@bug(True, reason="Can't succeed")
class Test_Failing:
    def test_success(self):
        """success test"""
        interfaces.library_stdout.assert_absence("nope i do not exists")

    def test_failing(self):
        """Failing test"""
        interfaces.library_stdout.assert_presence("nope i do not exists")


if __name__ == "__main__":
    sys.exit("Usage: pytest utils/test_the_test.py")
