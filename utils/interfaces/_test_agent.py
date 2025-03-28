import pathlib
import threading
import json
from utils.interfaces._core import InterfaceValidator
from utils._logger import logger
from utils._weblog import HttpResponse


class _TestAgentInterfaceValidator(InterfaceValidator):
    def __init__(self):
        super().__init__("test_agent")
        self.ready = threading.Event()
        self._data_traces_list = []
        self._data_telemetry_list = []

    def collect_data(self, interface_folder: str, agent_host: str = "localhost", agent_port: int = 8126):
        import ddapm_test_agent.client as agent_client

        logger.debug("Collecting data from test agent")
        client = agent_client.TestAgentClient(base_url=f"http://{agent_host}:{agent_port}")
        self._data_traces_list = client.traces(clear=False)
        if self._data_traces_list:
            pathlib.Path(f"{interface_folder}/00_traces.json").write_text(
                json.dumps(self._data_traces_list, indent=2), encoding="utf-8"
            )

        self._data_telemetry_list = client.telemetry(clear=False)
        if self._data_telemetry_list:
            pathlib.Path(f"{interface_folder}/00_telemetry.json").write_text(
                json.dumps(self._data_telemetry_list, indent=2), encoding="utf-8"
            )

    def get_traces(self, request: HttpResponse | None = None):
        rid = request.get_rid() if request else None
        if not rid:
            raise ValueError("Request ID not found")
        logger.debug(f"Try to find traces related to request {rid}")

        for data in self._data_traces_list:
            for data_received in data:
                if "trace_id" in data_received:
                    if "http.useragent" in data_received["meta"]:
                        if rid in data_received["meta"]["http.useragent"]:
                            return data_received
        return None

    def get_telemetry_for_runtime(self, runtime_id: str):
        logger.debug(f"Try to find telemetry data related to runtime-id {runtime_id}")
        assert runtime_id is not None, "Runtime ID not found"
        telemetry_msgs = []
        for data_received in self._data_telemetry_list:
            if data_received["runtime_id"] == runtime_id:
                telemetry_msgs.append(data_received)

        return telemetry_msgs

    def get_crashlog_for_runtime(self, runtime_id: str):
        logger.debug(f"Try to find a crashlog related to runtime-id {runtime_id}")
        assert runtime_id is not None, "Runtime ID not found"
        return [log for log in self.get_telemetry_logs() if log["runtime_id"] == runtime_id]

    def get_telemetry_for_autoinject(self):
        logger.debug("Try to find telemetry data related to autoinject")
        injection_metrics = []
        injection_metrics += [
            series
            for t in self._data_telemetry_list
            if t["request_type"] == "generate-metrics"
            for series in t["payload"]["series"]
            if str(series["metric"]).startswith("inject.")
        ]
        return injection_metrics

    def get_telemetry_for_autoinject_library_entrypoint(self):
        logger.debug("Try to find telemetry data related to the library entrypoint")
        injection_metrics = []
        injection_metrics += [
            series
            for t in self._data_telemetry_list
            if t["request_type"] == "generate-metrics"
            for series in t["payload"]["series"]
            if str(series["metric"]).startswith("library_entrypoint.")
        ]
        return injection_metrics

    def get_telemetry_logs(self):
        logger.debug("Try to find telemetry data related to logs")
        return [t for t in self._data_telemetry_list if t["request_type"] == "logs"]

    def get_crash_reports(self):
        logger.debug("Try to find telemetry data related to crash reports")
        crash_reports: list = []

        for t in self.get_telemetry_logs():
            payload = t["payload"]

            # If payload is a list, iterate through its items
            if isinstance(payload, list):
                crash_reports.extend(
                    p for p in payload if "signame" in p.get("tags", "") or "signum" in p.get("tags", "")
                )
            # If payload is a single object, check it directly
            elif isinstance(payload, dict):
                if "signame" in payload.get("tags", "") or "signum" in payload.get("tags", ""):
                    crash_reports.append(payload)

        return crash_reports
