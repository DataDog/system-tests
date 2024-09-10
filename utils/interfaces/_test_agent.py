import pathlib
import threading
import time
import json
from utils.interfaces._core import ProxyBasedInterfaceValidator
from utils.tools import logger, get_rid_from_span, get_rid_from_request


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

            # make 100% sure that the list is sorted
            # self._data_list.sort(key=lambda data: data["log_filename"])

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
        logger.debug(f"Try to find telemetry data related to autoinject")
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
