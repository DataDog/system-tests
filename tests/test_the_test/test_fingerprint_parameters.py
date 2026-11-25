from utils import scenarios
from utils._context.junit_parameters import fingerprint_parameters


@scenarios.test_the_test
def test_fingerprint_keeps_runtime_and_drops_component_versions() -> None:
    parameters = fingerprint_parameters(
        {
            "scenario": "DOCKER_SSI",
            "arch": "amd64",
            "os": "ubuntu_22",
            "installed_language_runtime": "25.0.5",
            "agent": "7.85.4-1",
            "library": {"name": "nodejs", "version": "7.0.0-pre"},
            "datadog-apm-inject": {"version": "v0.73.0-dev.abc"},
            "datadog-installer": {"version": "0.0.0"},
        }
    )

    assert parameters == {
        "scenario": "DOCKER_SSI",
        "arch": "amd64",
        "os": "ubuntu_22",
        "installed_language_runtime": "25.0.5",
        "library": {"name": "nodejs"},
    }
