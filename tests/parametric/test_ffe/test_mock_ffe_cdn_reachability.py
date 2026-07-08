"""Smoke-test Docker reachability for the host-backed mock FFE CDN fixture."""

from utils import features, scenarios
from utils._context.docker import get_docker_client
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures._mock_ffe_cdn import CONFIG_PATH, EXPECTED_API_KEY, MockFFECDNServer

pytest_plugins = ["utils.docker_fixtures._mock_ffe_cdn"]


@scenarios.parametric
@features.feature_flags_dynamic_evaluation
class Test_Feature_Flag_Mock_FFE_CDN_Reachability:
    """Validate the mock FFE CDN URL used by SDK containers is reachable from the test network."""

    def test_mock_ffe_cdn_reachable_from_test_agent_network(
        self, test_agent: TestAgentAPI, mock_ffe_cdn: MockFFECDNServer
    ) -> None:
        mock_ffe_cdn.set_response("valid")
        container = get_docker_client().containers.get(test_agent.container_name)
        script = "\n".join(
            [
                "import sys",
                "import urllib.request",
                (
                    "request = urllib.request.Request("
                    f"{mock_ffe_cdn.library_config_url!r}, "
                    f"headers={{'DD-API-KEY': {EXPECTED_API_KEY!r}}})"
                ),
                "response = urllib.request.urlopen(request, timeout=5)",
                "data = response.read(1)",
                "print(response.status)",
                "sys.exit(0 if response.status == 200 and data else 1)",
            ]
        )

        exit_code, output = container.exec_run(["python3", "-c", script], demux=True)
        stdout, stderr = output if output is not None else (b"", b"")
        assert exit_code == 0, (
            "mock FFE CDN was not reachable from the test-agent network; "
            f"stdout={(stdout or b'').decode('utf-8', errors='replace')!r}; "
            f"stderr={(stderr or b'').decode('utf-8', errors='replace')!r}"
        )

        status = mock_ffe_cdn.status()
        assert status["requests_total"] == 1
        assert status["last_auth_present"] is True
        assert status["last_path"] == CONFIG_PATH
        assert status["last_status_code"] == 200
