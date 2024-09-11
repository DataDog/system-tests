import threading
import json
from utils.interfaces._core import ProxyBasedInterfaceValidator
from utils.tools import logger, get_rid_from_request
import pathlib
import threading
import time
import json


class _TestAgentInterfaceValidator(ProxyBasedInterfaceValidator):
    def __init__(self):
        super().__init__("test_agent")
        self.ready = threading.Event()
        self._data_telemetery_list = []

    def ingest_file(self, src_path):
        self.ready.set()
        logger.debug(f"Test Agent Interface: Ingesting file {src_path}")
        with self._lock:
            if src_path in self._ingested_files:
                return

            logger.debug(f"Ingesting {src_path}")

            with open(src_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.decoder.JSONDecodeError:
                    # the file may not be finished
                    return
            if src_path.endswith("telemetry.json"):
                self._data_telemetery_list.append(data)
            else:
                self._append_data(data)
            self._ingested_files.add(src_path)

        if self._wait_for_function and self._wait_for_function(data):
            self._wait_for_event.set()

    def get_traces(self, request=None):
        rid = get_rid_from_request(request)
        if not rid:
            raise ValueError("Request ID not found")
        logger.debug(f"Try to find traces related to request {rid}")

        for data in self.get_data():
            for data_received in data[0]:
                if "trace_id" in data_received:
                    if "http.useragent" in data_received["meta"]:
                        if rid in data_received["meta"]["http.useragent"]:
                            return data_received
        return None

    def get_telemetry_for_runtime(self, runtime_id):
        logger.debug(f"Try to find telemetry data related to runtime-id {runtime_id}")
        assert runtime_id is not None, "Runtime ID not found"
        telemetry_msgs = []
        for telemetry_data in self._data_telemetery_list:
            for data_received in telemetry_data:
                if data_received["runtime_id"] == runtime_id:
                    telemetry_msgs.append(data_received)

        return telemetry_msgs

    def get_telemetry_for_autoinject(self):
        logger.debug("Try to find telemetry data related to autoinject")
        injection_metrics = []
        for telemetry_data in self._data_telemetery_list:
            injection_metrics += [
                series
                for t in telemetry_data
                if t["request_type"] == "generate-metrics"
                for series in t["payload"]["series"]
                if str(series["metric"]).startswith("inject.")
            ]
        return injection_metrics


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
                    pathlib.Path(f"{self._log_folder}/{_traces_count}_traces.json").write_text(
                        json.dumps(traces, indent=2), encoding="utf-8"
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
                    pathlib.Path(f"{self._log_folder}/{_telemetry_count}_telemetry.json").write_text(
                        json.dumps(telemetry_data, indent=2), encoding="utf-8"
                    )
                    _telemetry_count += 1
            except ValueError as e:
                raise e
            time.sleep(1)

    def start(self, log_folder):
        import ddapm_test_agent.client as agent_client

        self._log_folder = log_folder
        client = agent_client.TestAgentClient(base_url="http://localhost:8126")

        thread_traces = threading.Thread(target=self.get_traces, args=(client, 1))
        thread_telemetry = threading.Thread(target=self.get_telemetry, args=(client, 1))
        thread_traces.start()
        thread_telemetry.start()

    def stop(self):
        self._keep_polling = False
