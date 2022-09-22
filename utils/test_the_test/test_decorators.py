import sys
import logging

from utils import interfaces, bug, context, irrelevant, missing_feature, flaky, rfc, released
from utils.tools import logger
from utils._context.library_version import LibraryVersion


context.weblog_variant = "spring"
context.library = LibraryVersion("java", "0.66.0")
# monkey patch
context.execute_warmups = lambda *args, **kwargs: None


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


class Logs(list):
    def write(self, line):
        self.append(line)

    def __str__(self):
        return "\n".join([l.strip() for l in self])


logs = Logs()
handler = logging.StreamHandler(stream=logs)
logger.addHandler(handler)


@irrelevant(True)
class Test_IrrelevantClass:
    def test_method(self):
        raise Exception("Should not be executed")


@flaky(True)
class Test_FlakyClass:
    def test_method(self):
        raise Exception("Should not be executed")


@bug(True)
class Test_BugClass:
    executed = False

    def test_method(self):
        Test_BugClass.executed = True

    def test_xpassed_method(self):
        """This test will be reported as xpassed"""
        interfaces.library_stdout.add_assertion(True)


@released(java="?")
class Test_NotReleased:
    executed = False

    def test_method(self):
        Test_NotReleased.executed = True


class Test_Class:
    @irrelevant(True)
    def test_irrelevant_method(self):
        raise Exception("Should not be executed")

    @flaky(True)
    def test_flaky_method(self):
        raise Exception("Should not be executed")

    @irrelevant(condition=False)
    @flaky(condition=False)
    def test_good_method(self):
        pass

    @missing_feature(True, reason="missing feature")
    @irrelevant(True, reason="irrelevant")
    def test_skipping_prio(self):
        raise Exception("Should not be executed")

    @missing_feature(True, reason="missing feature")
    @irrelevant(True, reason="irrelevant")
    def test_skipping_prio2(self):
        raise Exception("Should not be executed")


class Test_Metadata:
    def test_rfc(self):
        @rfc("A link")
        class Test:
            pass

        assert Test.__rfc__ == "A link"

    def test_released(self):
        @released(java="0.1")
        @released(php="99.99")
        class Test:
            pass

        assert Test.__released__["java"] == "0.1"
        assert "php" not in Test.__released__

    def test_double_declaration(self):
        try:

            @released(java="99.99")
            @released(java="99.99")
            class Test:
                pass

        except ValueError as e:
            assert str(e) == "A java' version for Test has been declared twice"
        else:
            raise Exception("Component has been declared twice, should fail")

    def test_version_sugar_syntax(self):
        @released(java={"spring": "2.1", "vertx": "0.2"})
        class Test_DictBasic:
            pass

        assert Test_DictBasic.__released__["java"] == "2.1"
        assert (
            "Test_DictBasic => missing feature for java: release version is 2.1, tested version is 0.66.0 => xfail\n"
            in logs
        )

    def test_version_sugar_syntax_wildcard(self):
        @released(java={"*": "2.1", "vertx": "0.2"})
        class Test_DictBasic:
            pass

        assert Test_DictBasic.__released__["java"] == "2.1"
        assert (
            "Test_DictBasic => missing feature for java: release version is 2.1, tested version is 0.66.0 => xfail\n"
            in logs
        )


class Test_Skips:
    def test_irrelevant(self):
        assert is_skipped(Test_IrrelevantClass, "not relevant")
        assert is_skipped(Test_Class.test_irrelevant_method, "not relevant")

        assert "Test_IrrelevantClass => not relevant => skipped\n" in logs
        assert "test_irrelevant_method => not relevant => skipped\n" in logs

    def test_flaky(self):
        assert is_skipped(Test_FlakyClass, "known bug (flaky)")
        assert is_skipped(Test_Class.test_flaky_method, "known bug (flaky)")

        assert "Test_FlakyClass => known bug (flaky) => skipped\n" in logs
        assert "test_flaky_method => known bug (flaky) => skipped\n" in logs

    def test_regular(self):
        assert is_not_skipped(Test_Class)
        assert is_not_skipped(Test_Class.test_good_method)

    def test_double_skip(self):
        assert is_skipped(Test_Class.test_skipping_prio, "not relevant: irrelevant")
        assert is_skipped(Test_Class.test_skipping_prio, "missing feature: missing feature")

        assert is_skipped(Test_Class.test_skipping_prio2, "not relevant: irrelevant")
        assert is_skipped(Test_Class.test_skipping_prio2, "missing feature: missing feature")

    def test_bug(self):
        assert is_skipped(Test_BugClass, "known bug")
        assert Test_BugClass.executed, "Bug decorator execute the test"

        assert "Test_BugClass => known bug => xfail\n" in logs

    def test_not_released(self):
        assert is_skipped(Test_NotReleased, "missing feature: release not yet planned")
        assert Test_NotReleased.executed, "missing feature execute the test"


if __name__ == "__main__":
    sys.exit("Usage: pytest utils/test_the_test.py")
