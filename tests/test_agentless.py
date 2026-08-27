"""Direct-to-intake delivery (DD_AGENTLESS_ENABLED), without a Datadog Agent.

Endpoints below are derived from reading the tracer/libdatadog source on the (unmerged)
`bob/agentless-setting` branch of dd-trace-py, not from live-captured traffic. Re-confirm
against real proxy captures once the branch is buildable in this environment; see
utils/_context/_scenarios/agentless_endtoend.py and debugger_agentless.py for the scenario setup.
"""

from utils import features, interfaces, scenarios, weblog
from utils._context._scenarios.agentless_endtoend import AGENTLESS_MOCK_API_KEY
from utils._remote_config import send_apm_tracing_command
from utils.dd_constants import RemoteConfigApplyState as ApplyState

TRACE_SUBMISSION_PATH = "/v1/input"
TRACE_SUBMISSION_HOST = "browser-intake-mock-intake.invalid"

STATS_PATH = "/api/v0.2/stats"
STATS_HOST = "trace.agent.mock-intake.invalid"

RC_CONFIGURATIONS_PATH = "/api/v0.1/configurations"
RC_HOST = "config.mock-intake.invalid"


def _headers(request: dict) -> dict[str, str]:
    return {name.lower(): value for name, value in request["request"]["headers"]}


def _requests_at(host: str, path: str) -> list[dict]:
    return [data for data in interfaces.datadog_direct.get_data(path) if data["host"] == host]


@scenarios.apm_tracing_agentless
@features.not_reported
class Test_Agentless_Trace_Submission:
    """Traces are sent directly to the intake, bypassing the Datadog Agent."""

    def setup_trace_submission(self):
        self.r = weblog.get("/")

    def test_trace_submission(self):
        assert self.r.status_code == 200

        requests = _requests_at(TRACE_SUBMISSION_HOST, TRACE_SUBMISSION_PATH)
        assert len(requests) != 0, f"No request captured on {TRACE_SUBMISSION_HOST}{TRACE_SUBMISSION_PATH}"

        request = requests[-1]
        assert request["response"]["status_code"] // 100 == 2

        headers = _headers(request)
        assert headers["dd-api-key"] in {AGENTLESS_MOCK_API_KEY, "--redacted--"}

        content = request["request"]["content"]
        assert content, "Trace submission request body is empty"


@scenarios.apm_tracing_agentless
@features.client_side_stats_supported
class Test_Agentless_Stats:
    """Client-side trace stats are sent directly to the intake, on their own endpoint."""

    def setup_stats(self):
        self.r = weblog.get("/")

    def test_stats(self):
        assert self.r.status_code == 200

        stats_requests = _requests_at(STATS_HOST, STATS_PATH)
        assert len(stats_requests) != 0, f"No request captured on {STATS_HOST}{STATS_PATH}"

        request = stats_requests[-1]
        assert request["response"]["status_code"] // 100 == 2

        headers = _headers(request)
        assert headers["dd-api-key"] in {AGENTLESS_MOCK_API_KEY, "--redacted--"}

        # Stats and traces are distinct payloads on distinct hosts/paths.
        trace_requests = _requests_at(TRACE_SUBMISSION_HOST, TRACE_SUBMISSION_PATH)
        assert request not in trace_requests


@scenarios.apm_tracing_agentless
@features.remote_config_object_supported
class Test_Agentless_Remote_Config:
    """The native agentless Remote Configuration client polls the intake directly.

    There is no agent to relay client state via `/v0.7/config`: the native client polls
    `/api/v0.1/configurations` directly and reports its per-config apply state inline on that
    same request (LatestConfigsRequest.active_clients[0].state) instead of via a separate
    follow-up request. send_apm_tracing_command()/send_state() (utils/_remote_config.py) now
    detect this agentless shape (keyed off `context.scenario.include_agent`), so this drives a
    real config push and confirms application the same way agent-mode RC tests do.
    """

    def setup_remote_config_poll(self):
        self.rc_state = send_apm_tracing_command(dynamic_instrumentation_enabled=True)

    def test_remote_config_poll(self):
        assert self.rc_state.state == ApplyState.ACKNOWLEDGED, (
            f"RC config was not acknowledged: state={self.rc_state.state}, configs={self.rc_state.configs}"
        )
        for config in self.rc_state.configs.values():
            assert config.get("apply_state") != ApplyState.ERROR, f"RC config apply error: {config}"

        requests = _requests_at(RC_HOST, RC_CONFIGURATIONS_PATH)
        assert len(requests) != 0, f"No request captured on {RC_HOST}{RC_CONFIGURATIONS_PATH}"

        request = requests[-1]
        assert request["method"] == "POST"

        headers = _headers(request)
        assert headers["dd-api-key"] in {AGENTLESS_MOCK_API_KEY, "--redacted--"}
        assert headers.get("content-type") == "application/x-protobuf"
