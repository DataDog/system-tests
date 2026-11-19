from unittest.mock import MagicMock, patch

from utils import pytest, scenarios
from utils._context._scenarios.docker_ssi import _DockerSSIScenario
from utils._context.component_version import Version


def _scenario(
    *,
    library: str | None,
    injector: str | None,
    custom_library_version: str | None = None,
    custom_injector_version: str | None = None,
) -> _DockerSSIScenario:
    scenario = _DockerSSIScenario.__new__(_DockerSSIScenario)
    scenario.name = "DOCKER_SSI_SERVICENAMING"
    scenario.components = {}
    if library is not None:
        scenario.components["datadog-apm-library"] = Version(library)
    if injector is not None:
        scenario.components["datadog-apm-inject"] = Version(injector)
    scenario._env = "prod"  # noqa: SLF001
    scenario._custom_library_version = custom_library_version  # noqa: SLF001
    scenario._custom_injector_version = custom_injector_version  # noqa: SLF001
    return scenario


def _stdout_lines(stdout_mock: MagicMock) -> list[str]:
    return [str(call.args[0]) for call in stdout_mock.call_args_list]


@scenarios.test_the_test
def test_installed_library_and_injector_pass() -> None:
    scenario = _scenario(library="1.2.3", injector="0.72.0")

    with patch("utils._context._scenarios.docker_ssi.logger.stdout") as stdout:
        scenario.check_installed_components()

    assert any("All components are installed correctly" in line for line in _stdout_lines(stdout))


@scenarios.test_the_test
@pytest.mark.parametrize(
    ("library", "injector", "expected"),
    [
        (None, "0.72.0", "without installing the tracer library"),
        ("0.0.0", "0.72.0", "without installing the tracer library"),
        ("1.2.3", None, "without installing the injector"),
        ("1.2.3", "0.0.0", "without installing the injector"),
        ("0.0.0", "0.0.0", "without installing the tracer library and the injector"),
    ],
)
def test_missing_ssi_component_exits_with_code_3(library: str | None, injector: str | None, expected: str) -> None:
    scenario = _scenario(library=library, injector=injector)
    build_log = "logs_docker_ssi_servicenaming/docker_build.log"

    with (
        patch("utils._context._scenarios.docker_ssi.logger.stdout") as stdout,
        pytest.raises(pytest.exit.Exception, match=expected) as exc_info,
    ):
        scenario.check_installed_components()

    assert exc_info.value.returncode == 3
    lines = _stdout_lines(stdout)
    assert any(build_log in line for line in lines)
    assert any("environment to [prod]" in line for line in lines)


@scenarios.test_the_test
def test_custom_version_hints_are_kept_when_components_are_missing() -> None:
    scenario = _scenario(
        library="0.0.0",
        injector="0.0.0",
        custom_library_version="main",
        custom_injector_version="0.72.0-1",
    )

    with (
        patch("utils._context._scenarios.docker_ssi.logger.stdout") as stdout,
        pytest.raises(pytest.exit.Exception),
    ):
        scenario.check_installed_components()

    lines = "\n".join(_stdout_lines(stdout))
    assert "--ssi-library-version" in lines
    assert "[main]" in lines
    assert "--ssi-injector-version" in lines
    assert "[0.72.0-1]" in lines
