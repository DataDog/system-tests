import pathlib
import threading
import time
import json
import ddapm_test_agent.client as agent_client


class TestAgentClientPolling:
    def __init__(self) -> None:
        self._keep_polling = True
        self._log_folder = None

    def get_traces(self, client, num):
        _traces_count = 0
        while self._keep_polling:
            try:
                traces = client.traces(clear=False)
                if traces:
                    pathlib.Path(f"{self._log_folder}/{_traces_count}_traces.json", encoding="utf-8").write_text(
                        json.dumps(traces, indent=2)
                    )
                    _traces_count += 1
            except ValueError as e:
                raise e
            time.sleep(1)

    def get_telemetry(self, client, num):
        _telemetry_count = 0
        while self._keep_polling:
            try:
                telemetry_data = client.telemetry(clear=True)
                if telemetry_data:
                    pathlib.Path(f"{self._log_folder}/{_telemetry_count}_telemetry.json", encoding="utf-8").write_text(
                        json.dumps(telemetry_data, indent=2)
                    )
                    _telemetry_count += 1
            except ValueError as e:
                raise e
            time.sleep(1)

    def start(self, log_folder):
        self._log_folder = log_folder
        client = agent_client.TestAgentClient(base_url="http://localhost:8126")

        thread_traces = threading.Thread(target=self.get_traces, args=(client, 1))
        thread_telemetry = threading.Thread(target=self.get_telemetry, args=(client, 1))
        thread_traces.start()
        thread_telemetry.start()

    def stop(self):
        self._keep_polling = False
