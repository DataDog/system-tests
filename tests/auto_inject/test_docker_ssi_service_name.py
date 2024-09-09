from utils import scenarios, features, context
from utils.tools import logger
from utils import scenarios, features
import requests
import time
import ddapm_test_agent.client as agent_client
import json
import pathlib
from deepdiff import DeepDiff


@features.host_auto_installation_script
@scenarios.docker_ssi_service_name
class TestDockerSSIServiceName:
    def test_service_name(self):
        requests.get(
            context.scenario.weblog_url, timeout=10,
        )

        client = agent_client.TestAgentClient(base_url=f"http://localhost:8126")
        try:
            traces = self.wait_for_at_least_traces(client, 2)
            pathlib.Path(f"{context.scenario.host_log_folder}/traces.json").write_text(json.dumps(traces[0]))
        except ValueError as e:
            # Eat the execption if we haven't received a trace since we are going to assert on it latter
            if not str(e).startswith("Number (1) of traces not available from test agent, got 0:"):
                raise e

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
                    # logger.info(f"Traces received: {traces}")
                    return sorted(traces, key=lambda trace: trace[0]["start"], reverse=True)
            time.sleep(0.1)
        raise ValueError(
            "Number (%r) of traces not available from test agent, got %r:\n%r" % (num, num_received, traces)
        )

    def run_assertions(self):
        """ Let's compare the traces with the snapshot traces. There some field that allways change like timestamp, trace_id, span_id, start, duration..."""
        snapshot_traces = json.loads(pathlib.Path(f"tests/auto_inject/services/tomcat.json").read_text())
        current_traces = json.loads(pathlib.Path(f"{context.scenario.host_log_folder}/traces.json").read_text())
        ddiffs = DeepDiff(snapshot_traces, current_traces, ignore_order=True)

        # The difference should be only the valus_changed for some fields like timestamp, trace_id, span_id, start, duration....
        assert len(ddiffs.keys()) == 1, f"The current traces json file contains different fields. Diffs: {ddiffs}"

        # Values changed allowed fields
        allowed_fields = [
            "['trace_id']",
            "['span_id']",
            "['start']",
            "['duration']",
            "['metrics']['peer.port']",
            "['meta']['_dd.p.tid']",
            "['meta']['runtime-id']",
        ]

        for key in ddiffs["values_changed"]:
            # diff keys format examples: root[0]['span_id'], root[0]['start'], root[0]['duration'], root[0]['metrics']['peer.port'], root[0]['meta']['_dd.p.tid'], root[0]['meta']['runtime-id']
            assert (
                key.replace("root[0]", "") in allowed_fields
            ), f"Unexpected field found in the traces json file: {key}"
