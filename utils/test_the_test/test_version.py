from utils._context.library_version import LibraryVersion, Version
from utils import context

context.execute_warmups = lambda *args, **kwargs: None


def test_version_comparizon():

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


def test_version_serialization():

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


def test_library_version():

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
