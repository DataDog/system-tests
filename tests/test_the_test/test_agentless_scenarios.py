from utils import scenarios
from utils._context.containers import MOCKED_BACKEND_DOMAIN
from utils.proxy.mocked_response import MockedBackendResponse
from utils.proxy.rc_response_builder import build_rc_configurations_protobuf
from utils.proxy.tuf import get_tuf_root_json


@scenarios.test_the_test
def test_tracer_agentless_scenario_sends_everything_to_the_mocked_backend():
    scenario = scenarios.apm_tracing_agentless
    environment = scenario.weblog_infra.library_container.environment

    assert not scenario.include_agent
    assert scenario.mocked_backend_container.tls
    assert environment["DD_AGENTLESS_ENABLED"] == "true"
    # the intake hostnames derived from it are network aliases of the mocked backend
    assert environment["DD_SITE"] == MOCKED_BACKEND_DOMAIN
    assert environment["DD_API_KEY"] == scenario.weblog_api_key


@scenarios.test_the_test
def test_agentless_remote_config_is_served_by_the_mocked_backend():
    scenario = scenarios.debugger_agentless
    environment = scenario.weblog_infra.library_container.environment

    assert scenario.rc_api_enabled
    assert scenario.rc_backend_enabled
    # the native RC client trusts the test-signed responses
    assert environment["DD_REMOTE_CONFIGURATION_CONFIG_ROOT"] == get_tuf_root_json()
    assert environment["DD_REMOTE_CONFIGURATION_DIRECTOR_ROOT"] == get_tuf_root_json()

    # served from the first poll, until a test pushes its own
    (placeholder,) = scenario.mocked_backend_container.internal_mocked_responses
    assert isinstance(placeholder, MockedBackendResponse)
    assert placeholder.path == "/api/v0.1/configurations"
    assert placeholder.content == build_rc_configurations_protobuf(None)


@scenarios.test_the_test
def test_agentless_scenario_without_remote_config_has_no_mocked_response():
    scenario = scenarios.apm_tracing_agentless_fast_heartbeat

    assert not scenario.rc_api_enabled
    assert scenario.mocked_backend_container.internal_mocked_responses == []
