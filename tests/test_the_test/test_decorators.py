import sys
import logging

import pytest

from utils import irrelevant, missing_feature, flaky, rfc, context
from utils._decorators import released
from utils._context.library_version import LibraryVersion
from utils.tools import logger


pytestmark = pytest.mark.scenario("TEST_THE_TEST")


BASE_PATH = "tests/test_the_test/test_decorators.py"


def is_skipped(item, reason):
    if not hasattr(item, "pytestmark"):
        print(f"{item} has not pytestmark attribute")
    else:
        for mark in item.pytestmark:
            if mark.name in ("skip", "xfail"):

                if mark.kwargs["reason"] == reason:
                    print(f"Found expected {mark} for {item}")
                    return True

                print(f"{item} is skipped, but reason is {repr(mark.kwargs['reason'])} io {repr(reason)}")

    raise Exception(f"{item} is not skipped, or not with the good reason")


def is_not_skipped(item):
    if hasattr(item, "pytestmark"):
        for mark in item.pytestmark:
            if mark.name == ("skip", "xfail"):
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


class Test_Class:
    @irrelevant(condition=False)
    @flaky(condition=False)
    def test_good_method(self):
        pass


class Test_Metadata:
    def test_rfc(self):
        @rfc("A link")
        class Test:
            pass

    def test_library_does_not_exists(self):
        with pytest.raises(ValueError):

            @missing_feature(library="not a lib")
            def test_method():
                ...


class Test_Skips:
    def test_regular(self):
        assert is_not_skipped(Test_Class)
        assert is_not_skipped(Test_Class.test_good_method)


def test_version_range():
    def check(declaration, tested_version, should_be_skipped):
        class LocalClass:
            pass

        original_library = context.scenario.library  # not very clean, TODO: add a fixture for that purpose
        context.scenario.library = LibraryVersion("java", tested_version)
        decorated_class = released(java=declaration)(LocalClass)
        context.scenario.library = original_library

        if should_be_skipped:
            assert hasattr(decorated_class, "pytestmark")
            markers = decorated_class.pytestmark
            assert (
                markers[0].kwargs["reason"]
                == f"missing_feature for java: declared released version is {declaration}, tested version is {tested_version}"
            )
        else:
            assert not hasattr(decorated_class, "pytestmark")

    declaration = "^1.2.3 || ^2.3.4 || >=3.4.5"

    check(declaration, "1.2.2", should_be_skipped=True)
    check(declaration, "1.2.3", should_be_skipped=False)
    check(declaration, "1.9.9", should_be_skipped=False)
    check(declaration, "2.0.0", should_be_skipped=True)
    check(declaration, "2.3.3", should_be_skipped=True)
    check(declaration, "2.3.4", should_be_skipped=False)
    check(declaration, "2.9.9", should_be_skipped=False)
    check(declaration, "3.0.0", should_be_skipped=True)
    check(declaration, "3.4.4", should_be_skipped=True)
    check(declaration, "3.4.5", should_be_skipped=False)
    check(declaration, "3.9.9", should_be_skipped=False)
    check(declaration, "4.0.0", should_be_skipped=False)


if __name__ == "__main__":
    sys.exit("Usage: pytest utils/test_the_test.py")
