from pathlib import Path
from unittest.mock import MagicMock

from utils import pytest, scenarios
from utils._context._scenarios._core.sca import configure_sca_advisories
from utils._context.containers import TestedContainer as _TestedContainer


@scenarios.test_the_test
@pytest.mark.parametrize("library", ["java", "python", "java_lambda", "python_lambda"])
def test_sca_catalog_override_preserves_container_configuration(library: str) -> None:
    container = MagicMock(spec=_TestedContainer)
    container.image = MagicMock(labels={"system-tests-library": library})
    container.environment = {"JAVA_TOOL_OPTIONS": "-javaagent:/opt/dd-java-agent.jar", "DD_APPSEC_SCA_ENABLED": "true"}
    tracer_mount = {"bind": "/volumes/dd-trace-py", "mode": "ro"}
    container.volumes = {"./binaries/dd-trace-py": tracer_mount}

    configure_sca_advisories(container)

    source = f"./tests/appsec/sca/{library.removesuffix('_lambda')}/advisories.json"
    assert Path(source).is_file()
    assert container.volumes == {
        "./binaries/dd-trace-py": tracer_mount,
        source: {"bind": "/sca/advisories.json", "mode": "ro"},
    }
    assert container.environment == {
        "JAVA_TOOL_OPTIONS": "-javaagent:/opt/dd-java-agent.jar",
        "DD_APPSEC_SCA_ENABLED": "true",
        "_DD_APPSEC_SCA_CVE_FILE": "/sca/advisories.json",
    }
