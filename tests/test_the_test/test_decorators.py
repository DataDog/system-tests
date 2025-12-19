import sys
import logging
from typing import Any
import pytest

from utils import irrelevant, missing_feature, flaky, rfc, logger


pytestmark = pytest.mark.scenario("TEST_THE_TEST")


BASE_PATH = "tests/test_the_test/test_decorators.py"


def is_skipped(item: Any, reason: str):  # noqa: ANN401
    if not hasattr(item, "pytestmark"):
        logger.debug(f"{item} has not pytestmark attribute")
    else:
        for mark in item.pytestmark:
            if mark.name in ("skip", "xfail"):
                if mark.kwargs["reason"] == reason:
                    logger.debug(f"Found expected {mark} for {item}")
                    return True

                logger.debug(f"{item} is skipped, but reason is {mark.kwargs['reason']!r} io {reason!r}")

    raise Exception(f"{item} is not skipped, or not with the good reason")


def is_not_skipped(item):  # noqa: ANN001
    if hasattr(item, "pytestmark"):
        for mark in item.pytestmark:
            if mark.name == ("skip", "xfail"):
                raise Exception(f"{item} is skipped")

    return True


class Logs(list):
    def write(self, line: str):
        self.append(line)

    def __str__(self):
        return "\n".join([line.strip() for line in self])


logs = Logs()
handler = logging.StreamHandler(stream=logs)
logger.addHandler(handler)


class Test_Class:
    @irrelevant(condition=False)
    @flaky(condition=False, reason="FAKE-001")
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
            def test_method(): ...


class Test_Skips:
    def test_regular(self):
        assert is_not_skipped(Test_Class)
        assert is_not_skipped(Test_Class.test_good_method)


if __name__ == "__main__":
    sys.exit("Usage: pytest utils/test_the_test.py")
