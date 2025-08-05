import pathlib
import threading
import json
from utils.interfaces._core import InterfaceValidator
from utils._logger import logger
from utils._weblog import HttpResponse
from utils.tools import get_rid_from_span


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
        # TODO(munir): rename this method. This method returns a span
        # and not return traces.
        rid = request.get_rid() if request else None
        if not rid:
            raise ValueError("Request ID not found")
        logger.debug(f"Try to find traces related to request {rid}")

        for trace in self._data_traces_list:
            for span in trace:
                if rid == get_rid_from_span(span):
                    return span
        return None

    def get_telemetry_for_runtime(self, runtime_id: str | None):
        logger.debug(f"Try to find telemetry data related to runtime-id {runtime_id}")
        telemetry_msgs = []
        for data_received in self._data_telemetry_list:
            if runtime_id and data_received["runtime_id"] != runtime_id:
                continue
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

    def get_injection_metadata_for_autoinject(self):
        logger.debug("Try to find injection metadata related to autoinject")
        return [t["payload"] for t in self._data_telemetry_list if t["request_type"] == "injection-metadata"]

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
                    p
                    for p in payload
                    if "si_signo" in p.get("tags", "")
                    or "signame" in p.get("tags", "")
                    or "signum" in p.get("tags", "")
                )
            # If payload is a single object, check it directly
            elif isinstance(payload, dict):
                if (
                    "si_signo" in payload.get("tags", "")
                    or "signame" in payload.get("tags", "")
                    or "signum" in payload.get("tags", "")
                ):
                    crash_reports.append(payload)

        return crash_reports

    def get_telemetry_configurations(self, service_name: str | None = None, runtime_id: str | None = None) -> dict:
        """Get telemetry configurations for a given runtime ID and service name."""
        configurations = {}
        # Sort telemetry requests by timestamp, this ensures later configurations take precedence
        requests = list(self.get_telemetry_for_runtime(runtime_id))
        requests.sort(key=lambda x: x["tracer_time"])
        for request in requests:
            if service_name is not None and request["application"]["service_name"] != service_name:
                # Check if the service name in telemetry matches the expected service name
                logger.debug(
                    f"Service name in telemetry in requests: {request} "
                    f"does not match expected service name {service_name}"
                )
                continue
            # Convert all telemetry payloads to the the message-batch format. This simplifies configuration extraction
            events = (
                request["payload"]
                if request["request_type"] == "message-batch"
                else [{"payload": request.get("payload", {}), "request_type": request["request_type"]}]
            )
            logger.debug("Found teleemtry events: %s", events)
            for event in events:
                # Get the configuration from app-started or app-client-configuration-change payloads
                if event and event["request_type"] in ("app-started", "app-client-configuration-change"):
                    for config in event["payload"].get("configuration", []):
                        configurations[config["name"]] = config
        return configurations
