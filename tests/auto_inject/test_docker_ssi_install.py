from utils import scenarios, features, bug, flaky, context
from utils.tools import logger
from utils import scenarios, features
import tests.auto_inject.utils as base
import requests
import time
import ddapm_test_agent.client as agent_client
import json
import pathlib


@features.host_auto_installation_script
@scenarios.docker_ssi
class TestDockerSSIInstall:
    def test_install(self):
        self._test_install()

    def _test_install(self):
        requests.get(
            context.scenario.weblog_url, timeout=10,
        )

        client = agent_client.TestAgentClient(base_url=f"http://localhost:8126")

        try:
            traces = self.wait_for_at_least_traces(client, 1)
            pathlib.Path(f"{context.scenario.host_log_folder}/traces.json").write_text(json.dumps(traces))
        except ValueError as e:
            # Eat the execption if we haven't received a trace since we are going to assert on it latter
            if not str(e).startswith("Number (1) of traces not available from test agent, got 0:"):
                raise e

        telemetry = client.telemetry()
        pathlib.Path(f"{context.scenario.host_log_folder}/telemetry.json").write_text(json.dumps(telemetry))

        self.run_assertions()

    def wait_for_at_least_traces(
        self, client: agent_client.TestAgentClient, num: int, clear: bool = False, wait_loops: int = 30,
    ):
        num_received = 0
        traces = []
        for _ in range(wait_loops):
            try:
                traces = client.traces(clear=False)
            except requests.exceptions.RequestException:
                pass
            else:
                num_received = len(traces)
                if num_received >= num:
                    if clear:
                        client.clear()
                    return sorted(traces, key=lambda trace: trace[0]["start"])
            time.sleep(0.1)
        raise ValueError(
            "Number (%r) of traces not available from test agent, got %r:\n%r" % (num, num_received, traces)
        )

    def run_assertions(self):
        telemetry = json.loads(pathlib.Path(f"{context.scenario.host_log_folder}/telemetry.json").read_text())
        injection_metric = [
            series
            for t in telemetry
            if t["request_type"] == "generate-metrics"
            for series in t["payload"]["series"]
            if str(series["metric"]).startswith("inject.")
        ]
        assert len(injection_metric) >= 1
        assert injection_metric[0]["metric"] == "inject.success"
        assert pathlib.Path(f"{context.scenario.host_log_folder}/traces.json").exists()
        logger.info("OK DONE!!!")
