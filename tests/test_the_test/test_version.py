import pytest
import semantic_version as semver
from utils._decorators import CustomSpec
from utils._context.component_version import ComponentVersion, Version


pytestmark = pytest.mark.scenario("TEST_THE_TEST")


def test_version_comparizon():
    v = Version("1.0")

    assert v == "1.0"
    assert v != "1.1"

    assert v <= "1.1"
    assert v <= "1.0"
    assert v <= "1.1"
    assert v <= "1.0"

    assert v < "1.1"
    assert v < "1.1"

    assert v >= "0.9"
    assert v >= "1.0"
    assert v >= "0.9"
    assert v >= "1.0"

    assert v > "0.9"
    assert v > "0.9"

    assert str(Version("v1.3.1")) == "1.3.1"

    v = Version("0.53.0.dev70+g494e6dc0")
    assert v == "0.53.0.dev70+g494e6dc0"
    assert str(v) == "0.53.0+dev70.g494e6dc0"


def test_ruby_version():
    v = ComponentVersion("ruby", "0.53.0.appsec.180045")
    assert str(v.version) == "0.53.1-appsec+180045"

    v = ComponentVersion("ruby", "1.0.0.beta1 de82857")
    assert v.version == Version("1.0.1-beta1+de82857")

    v = ComponentVersion("ruby", "2.3.0 7dbcc40")
    assert str(v.version) == "2.3.1-z+7dbcc40"

    assert ComponentVersion("ruby", "1.0.0.beta1") == "ruby@1.0.1-z+beta1"
    assert ComponentVersion("ruby", "1.0.0.beta1 de82857") == "ruby@1.0.1-beta1+de82857"

    # very particular use case, because we hack the path for dev versions
    assert ComponentVersion("ruby", "1.0.0.beta1 de82857") < "ruby@1.0.1"
    assert ComponentVersion("ruby", "1.0.0.rc1") < "ruby@1.0.1"

    assert ComponentVersion("ruby", "2.3.0 7dbcc40") >= "ruby@2.3.1-dev"


def test_library_version_comparizon():
    assert ComponentVersion("x", "1.31.1") < "x@1.34.1"
    assert ComponentVersion("x", "v1.34.1") > "x@1.31.1"
    assert ComponentVersion("x", "1.31.1") < ComponentVersion("x", "v1.34.1")

    assert ComponentVersion("python", "1.1.0rc2.dev15+gc41d325d") >= "python@1.1.0rc2.dev"
    assert ComponentVersion("python", "1.1.0") > "python@1.1.0rc2.dev"

    assert ComponentVersion("python", "2.1.0-dev") < "python@2.1.0.dev83+gac1037728"
    assert ComponentVersion("python", "2.1.0-dev") < "python@2.1.0"

    assert ComponentVersion("nodejs", "6.0.0-pre") > "nodejs@5.0.0"
    assert ComponentVersion("nodejs", "5.0.0") <= "nodejs@6.0.0-pre"


def test_spec():
    assert semver.Version("6.0.0-pre") in CustomSpec(">=5.0.0")
    assert semver.Version("1.2.5-rc1") in CustomSpec(">1.2.4-rc1")
    assert semver.Version("1.3.0-rc1") in CustomSpec(">1.2.4-rc1")

    assert semver.Version("1.2.4") in CustomSpec(">1.2.3")
    assert semver.Version("1.2.4-rc1") in CustomSpec(">1.2.3")
    assert semver.Version("1.2.4") in CustomSpec(">1.2.4-rc1")

    assert semver.Version("1.2.4-rc1") in CustomSpec("<1.2.4")
    assert semver.Version("1.2.3") in CustomSpec("<1.2.4")
    assert semver.Version("1.2.3") in CustomSpec("<1.2.4-rc1")

    assert semver.Version("3.1.2") in CustomSpec(">=5.0.0 || ^3.0.0")
    assert semver.Version("4.1.2") not in CustomSpec(">=5.0.0 || ^3.0.0")
    assert semver.Version("6.0.0") in CustomSpec(">=5.0.0 || ^3.0.0")


def test_version_serialization():
    assert ComponentVersion("cpp", "v1.3.1") == "cpp@1.3.1"

    v = ComponentVersion("libddwaf", "* libddwaf (1.0.14.1.0.beta1)")
    assert v.version == Version("1.0.14.1.0.beta1")
    assert v.version == "1.0.14+1.0.beta1"

    v = ComponentVersion("php", "1.0.0-nightly")
    assert v.version == "1.0.0-nightly"

    v = ComponentVersion("nodejs", "3.0.0-pre0")
    assert v.version == "3.0.0-pre0"

    v = ComponentVersion("agent", "7.43.1-beta-cache-hit-ratio")
    assert v.version == "7.43.1-beta-cache-hit-ratio"

    v = ComponentVersion("agent", "7.50.0-dbm-oracle-0.1")
    assert str(v.version) == "7.50.0-dbm-oracle-0.1"


def test_agent_version():
    v = ComponentVersion("agent", "7.54.0-installer-0.0.7+git.106.b0943ad")
    assert v == "agent@7.54.0-installer-0.0.7+git.106.b0943ad"


def test_in_operator():
    v = ComponentVersion("p", "1.0")

    assert v in ("p@1.0", "p@1.1")
    assert v not in ("p@1.1", "p@1.2")
    assert v not in ("a@1.0", "p@1.1")


def test_library_version():
    v = ComponentVersion("p")
    assert v == "p"
    assert v != "u"

    v = ComponentVersion("p", "1.0")

    assert v == "p@1.0"
    assert v == "p"
    assert v != "p@1.1"
    assert v != "u"

    assert v <= "p@1.1"
    assert v <= "p@1.0"
    assert v <= "p@1.1"
    assert v <= "p@1.0"

    assert v < "p@1.1"
    assert v < "p@1.1"

    assert v >= "p@0.9"
    assert v >= "p@1.0"
    assert v >= "p@0.9"
    assert v >= "p@1.0"

    assert v > "p@0.9"
    assert v > "p@0.9"

    assert (v <= "u@1.0") is False
    assert (v >= "u@1.0") is False

    assert (v >= "u@1.0") is False
    assert (v <= "u@1.0") is False

    v = ComponentVersion("p")

    assert (v == "u@1.0") is False
    assert (v >= "u@1.0") is False

    v = ComponentVersion("python", "0.53.0.dev70+g494e6dc0")
    assert v == "python@0.53.0.dev70+g494e6dc0"

    v = ComponentVersion("java", "0.94.1~dde6877139")
    assert v == "java@0.94.1+dde6877139"
    assert v >= "java@0.94.1"
    assert v < "java@0.94.2"

    v = ComponentVersion("java", "0.94.0-SNAPSHOT~57664cfbe5")
    assert v == "java@0.94.0-SNAPSHOT+57664cfbe5"
    assert v < "java@0.94.0"
    assert v < "java@0.94.1"

    assert ComponentVersion("agent", "7.39.0-devel") == "agent@7.39.0-devel"


def test_php_version():
    v1 = ComponentVersion("php", "1.8.9")
    v2 = ComponentVersion("php", "1.9.0-prerelease")
    v3 = ComponentVersion("php", "1.9.0")
    v4 = ComponentVersion("php", "1.9.0+7ab1806dec09cbf6e7079ac59453b79fc5e9c91f")

    assert v3 == "php@v1.9.0"

    assert v1 < v2
    assert v1 < v3
    assert v2 < v3
    assert v3 <= v4

    # PHP may use a `-` to separate the version from the build
    # system-tests then replace the `-` with a `+`
    v5 = ComponentVersion("php", "1.9.0-7ab1806dec09cbf6e7079ac59453b79fc5e9c91f")  # hacked
    assert str(v5.version) == "1.9.0+7ab1806dec09cbf6e7079ac59453b79fc5e9c91f"
    assert v3 <= v5

    # but legit pre-release names are kept untouched
    assert str(ComponentVersion("php", "1.9.0-prerelease").version) == "1.9.0-prerelease"
    assert str(ComponentVersion("php", "1.9.0-dev").version) == "1.9.0-dev"
