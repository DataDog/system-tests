import pytest
from utils._context.library_version import LibraryVersion, Version


pytestmark = pytest.mark.scenario("TEST_THE_TEST")


def test_version_comparizon():

    v = Version("1.0")

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

    assert str(Version("v1.3.1")) == "1.3.1"

    v = Version("0.53.0.dev70+g494e6dc0")
    assert v == "0.53.0.dev70+g494e6dc0"
    assert str(v) == "0.53.0+dev70.g494e6dc0"


def test_library_version_comparizon():

    assert LibraryVersion("x", "1.31.1") < "x@1.34.1"
    assert "x@1.31.1" < LibraryVersion("x", "v1.34.1")
    assert LibraryVersion("x", "1.31.1") < LibraryVersion("x", "v1.34.1")

    assert LibraryVersion("ruby", "  * ddtrace (1.0.0.beta1)") == LibraryVersion("ruby", "1.0.0.beta1")
    assert LibraryVersion("ruby", "  * ddtrace (1.0.0.beta1)")
    assert LibraryVersion("ruby", "  * ddtrace (1.0.0.beta1 de82857)") < LibraryVersion("ruby", "1.0.0")
    assert LibraryVersion("ruby", "  * ddtrace (1.0.0.rc1)") < LibraryVersion("ruby", "1.0.0")

    assert LibraryVersion("python", "1.1.0rc2.dev15+gc41d325d") >= "python@1.1.0rc2.dev"
    assert LibraryVersion("python", "1.1.0") > "python@1.1.0rc2.dev"

    assert LibraryVersion("python", "2.1.0-dev") < "python@2.1.0.dev83+gac1037728"
    assert LibraryVersion("python", "2.1.0-dev") < "python@2.1.0"


def test_version_serialization():

    assert LibraryVersion("cpp", "v1.3.1") == "cpp@1.3.1"

    v = LibraryVersion("ruby", "  * ddtrace (0.53.0.appsec.180045)")
    assert v.version == Version("0.53.0-appsec.180045")
    assert v.version == "0.53.0-appsec.180045"

    v = LibraryVersion("ruby", "  * ddtrace (1.0.0.beta1)")
    assert v.version == Version("1.0.0-beta1")

    v = LibraryVersion("ruby", "  * ddtrace (1.0.0.beta1 de82857)")
    assert v.version == Version("1.0.0-beta1+de82857")

    v = LibraryVersion("libddwaf", "* libddwaf (1.0.14.1.0.beta1)")
    assert v.version == Version("1.0.14.1.0.beta1")
    assert v.version == "1.0.14+1.0.beta1"

    v = LibraryVersion("agent", "Agent 7.33.0 - Commit: e6cfcb9 - Serialization version: v5.0.4 - Go version: go1.16.7")
    assert v.version == "7.33.0"

    v = LibraryVersion("php", "1.0.0-nightly")
    assert v.version == "1.0.0"

    v = LibraryVersion("nodejs", "3.0.0-pre0")
    assert v.version == "3.0.0-pre0"

    v = LibraryVersion("agent", "7.43.1-beta-cache-hit-ratio")
    assert v.version == "7.43.1-beta-cache-hit-ratio"

    v = LibraryVersion("agent", "7.50.0-dbm-oracle-0.1")
    assert str(v.version) == "7.50.0-dbm-oracle-0.1"


def test_agent_version():

    v = LibraryVersion(
        "agent", "Agent 7.37.0 - Commit: 1124d66 - Serialization version: v5.0.22 - Go version: go1.17.11"
    )
    assert v == "agent@7.37.0"

    v = LibraryVersion(
        "agent",
        "Agent 7.38.0-rc.1 - Meta: git.1.3b34941 - Commit: 3b34941 - Serialization version: v5.0.23 - Go version: go1.17.11",
    )
    assert v == "agent@7.38.0-rc.1"

    v = LibraryVersion("agent", "Agent \x1b[36m7.40.0-rc.2\x1b[0m")
    assert v == "agent@7.40.0-rc.2"


def test_in_operator():
    v = LibraryVersion("p", "1.0")

    assert v in ("p@1.0", "p@1.1")
    assert v not in ("p@1.1", "p@1.2")
    assert v not in ("a@1.0", "p@1.1")


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

    assert LibraryVersion("agent", "7.39.0-devel") == "agent@7.39.0-devel"
