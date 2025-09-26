import sys
import logging

import pytest

from utils import irrelevant, missing_feature, flaky, rfc, logger, scenarios
from utils._decorators import released
from utils._context.component_version import ComponentVersion


pytestmark = pytest.mark.scenario("TEST_THE_TEST")


BASE_PATH = "tests/test_the_test/test_decorators.py"


def is_skipped(item, reason):
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


def test_version_range():
    def check(declaration, tested_version, should_be_skipped):
        class LocalClass:
            pass

        agent_version = scenarios.test_the_test.agent_version  # not very clean, TODO: add a fixture for that purpose
        scenarios.test_the_test.agent_version = ComponentVersion("agent", tested_version).version
        decorated_class = released(agent=declaration)(LocalClass)
        scenarios.test_the_test.agent_version = agent_version

        if should_be_skipped:
            assert hasattr(decorated_class, "pytestmark")
            markers = decorated_class.pytestmark
            assert (
                markers[0].kwargs["reason"]
                == f"missing_feature (declared version for agent is {declaration}, tested version is {tested_version})"
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
