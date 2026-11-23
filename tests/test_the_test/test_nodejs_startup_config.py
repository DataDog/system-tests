import json
from unittest.mock import Mock

from tests.parametric.conftest import APMLibrary, nodejs_startup_config
from utils import pytest, scenarios


@scenarios.test_the_test
@pytest.mark.parametrize("structured", [False, True], ids=["plain", "json"])
def test_nodejs_startup_config_reads_the_configuration(*, structured: bool) -> None:
    configuration = {"agent_url": "http://[::1]:8126", "debug": True, "tags": {"example": 'value with "quotes"'}}
    message = f"DATADOG TRACER CONFIGURATION - {json.dumps(configuration)}"
    line = json.dumps({"status": "info", "message": message}) if structured else message
    library = Mock(spec=APMLibrary)
    library.get_logs.return_value = f"Server ready\n{line}\n"

    assert nodejs_startup_config(library) == configuration


@scenarios.test_the_test
def test_nodejs_startup_config_ignores_markers_outside_log_messages() -> None:
    library = Mock(spec=APMLibrary)
    library.get_logs.return_value = "\n".join(
        json.dumps({"label": "DATADOG TRACER CONFIGURATION - {}", **fields})
        for fields in ({}, {"message": "Server ready"})
    )

    with pytest.raises(AssertionError, match="No .*DATADOG TRACER CONFIGURATION"):
        nodejs_startup_config(library)
