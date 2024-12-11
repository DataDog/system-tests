import asyncio
from collections import defaultdict
import json
import logging
import os
from datetime import datetime, UTC

from mitmproxy import master, options, http
from mitmproxy.addons import errorcheck, default_addons
from mitmproxy.flow import Error as FlowError, Flow

from _deserializer import deserialize

# prevent permission issues on file created by the proxy when the host is linux
os.umask(0)

logger = logging.getLogger(__name__)

SIMPLE_TYPES = (bool, int, float, type(None))

# the proxy determine the origin of the request based on the port
PORT_DIRECT_INTERACTION = 9000
PORT_WEBLOG = 9001
PORT_NODEJS_BUDDY = 9002
PORT_JAVA_BUDDY = 9003
PORT_RUBY_BUDDY = 9004
PORT_GOLANG_BUDDY = 9005
PORT_PYTHON_BUDDY = 9006
PORT_AGENT = 9100

messages_counts = defaultdict(int)


class CustomFormatter(logging.Formatter):
    def __init__(self, keys: list[str], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._keys = keys

    def format(self, record):
        result = super().format(record)

        for key in self._keys:
            result = result.replace(key, "{redacted-by-system-tests-proxy}")

        return result


class ObjectDumpEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, bytes):
            return str(o)
        return json.JSONEncoder.default(self, o)


class _RequestLogger:
    def __init__(self) -> None:
        self._keys = [
            os.environ.get("DD_API_KEY"),
            os.environ.get("DD_APPLICATION_KEY"),
            os.environ.get("DD_APP_KEY"),
        ]

        self._keys = [key for key in self._keys if key is not None]

        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        formatter = CustomFormatter(
            fmt="%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s", datefmt="%H:%M:%S", keys=self._keys
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        self.host_log_folder = os.environ.get("SYSTEM_TESTS_HOST_LOG_FOLDER", "logs")

        # request -> original port
        # as the port is overwritten at request stage, we loose it on response stage
        # this property will keep it
        self.original_ports = {}

        self.rc_api_enabled = os.environ.get("SYSTEM_TESTS_RC_API_ENABLED") == "True"
        self.span_meta_structs_disabled = os.environ.get("SYSTEM_TESTS_AGENT_SPAN_META_STRUCTS_DISABLED") == "True"

        span_events = os.environ.get("SYSTEM_TESTS_AGENT_SPAN_EVENTS")
        self.span_events = True if span_events == "True" else (False if span_events == "False" else None)

        self.rc_api_command = None

        # mimic the old API
        self.rc_api_sequential_commands = None
        self.rc_api_runtime_ids_request_count = None

    def _scrub(self, content):
        if isinstance(content, str):
            for key in self._keys:
                content = content.replace(key, "{redacted-by-system-tests-proxy}")

            return content

        if isinstance(content, (list, set, tuple)):
            return [self._scrub(item) for item in content]

        if isinstance(content, dict):
            return {key: self._scrub(value) for key, value in content.items()}

        if isinstance(content, SIMPLE_TYPES):
            return content

        logger.error(f"Can't scrub type {type(content)}")
        return "Content not properly deserialized by system-tests proxy. Please reach #apm-shared-testing on slack."

    @staticmethod
    def get_error_response(message):
        logger.error(message)
        return http.Response.make(400, message)

    def request(self, flow: Flow):

        logger.info(f"{flow.request.method} {flow.request.pretty_url}")

        if flow.request.port == PORT_DIRECT_INTERACTION:
            if not self.rc_api_enabled:
                flow.response = self.get_error_response(b"RC API is not enabled")
            elif flow.request.path == "/unique_command":
                logger.info("Store RC command to mock")
                self.rc_api_command = flow.request.content
                flow.response = http.Response.make(200, b"Ok")
            elif flow.request.path == "/sequential_commands":
                logger.info("Reset mocked RC sequential commands")
                self.rc_api_sequential_commands = json.loads(flow.request.content)
                self.rc_api_runtime_ids_request_count = defaultdict(int)
                flow.response = http.Response.make(200, b"Ok")
            else:
                flow.response = http.Response.make(404, b"Not found")

            return

        self.original_ports[flow.id] = flow.request.port

        if flow.request.port in (
            PORT_WEBLOG,
            PORT_PYTHON_BUDDY,
            PORT_NODEJS_BUDDY,
            PORT_JAVA_BUDDY,
            PORT_RUBY_BUDDY,
            PORT_GOLANG_BUDDY,
        ):

            if flow.request.headers.get("dd-protocol") == "otlp":
                # OTLP ingestion
                otlp_path = flow.request.headers.get("dd-otlp-path")
                if otlp_path == "agent":
                    flow.request.host = "agent"
                    flow.request.port = 4318
                    flow.request.scheme = "http"
                elif otlp_path == "collector":
                    flow.request.host = "system-tests-collector"
                    flow.request.port = 4318
                    flow.request.scheme = "http"
                elif otlp_path == "intake-traces":
                    flow.request.host = "trace.agent." + os.environ.get("DD_SITE", "datad0g.com")
                    flow.request.port = 443
                    flow.request.scheme = "https"
                elif otlp_path == "intake-metrics":
                    flow.request.host = "api." + os.environ.get("DD_SITE", "datad0g.com")
                    flow.request.port = 443
                    flow.request.scheme = "https"
                elif otlp_path == "intake-logs":
                    flow.request.host = "http-intake.logs." + os.environ.get("DD_SITE", "datad0g.com")
                    flow.request.port = 443
                    flow.request.scheme = "https"
                else:
                    raise Exception(f"Unknown OTLP ingestion path {otlp_path}")
            else:
                flow.request.host, flow.request.port = "agent", 8127
                flow.request.scheme = "http"

            logger.info(f"    => reverse proxy to {flow.request.pretty_url}")

    @staticmethod
    def request_is_from_tracer(request):
        return request.host == "agent"

    def response(self, flow):
        if flow.request.port == PORT_DIRECT_INTERACTION:
            return

        try:
            logger.info(f"    => Response {flow.response.status_code}")

            self._modify_response(flow)

            # get the interface name
            if flow.request.headers.get("dd-protocol") == "otlp":
                interface = "open_telemetry"
            elif self.request_is_from_tracer(flow.request):
                port = self.original_ports[flow.id]
                if port == PORT_WEBLOG:
                    interface = "library"
                # elif port == 80:  # UDS mode  # REALLY ?
                #     interface = "library"
                elif port == PORT_PYTHON_BUDDY:
                    interface = "python_buddy"
                elif port == PORT_NODEJS_BUDDY:
                    interface = "nodejs_buddy"
                elif port == PORT_JAVA_BUDDY:
                    interface = "java_buddy"
                elif port == PORT_RUBY_BUDDY:
                    interface = "ruby_buddy"
                elif port == PORT_GOLANG_BUDDY:
                    interface = "golang_buddy"
                elif port == PORT_PYTHON_BUDDY:
                    interface = "python_buddy"
                else:
                    raise ValueError(f"Unknown port provenance for {flow.request}: {port}")
            else:
                interface = "agent"

            # extract url info
            if "?" in flow.request.path:
                path, query = flow.request.path.split("?", 1)
            else:
                path, query = flow.request.path, ""

            # get destination
            message_count = messages_counts[interface]
            messages_counts[interface] += 1
            log_foldename = f"{self.host_log_folder}/interfaces/{interface}"
            export_content_files_to = f"{log_foldename}/files"
            log_filename = f"{log_foldename}/{message_count:05d}_{path.replace('/', '_')}.json"

            data = {
                "log_filename": log_filename,
                "path": path,
                "query": query,
                "host": flow.request.host,
                "port": flow.request.port,
                "request": {
                    "timestamp_start": datetime.fromtimestamp(flow.request.timestamp_start, tz=UTC).isoformat(),
                    "headers": list(flow.request.headers.items()),
                    "length": len(flow.request.content) if flow.request.content else 0,
                },
                "response": {
                    "status_code": flow.response.status_code,
                    "headers": list(flow.response.headers.items()),
                    "length": len(flow.response.content) if flow.response.content else 0,
                },
            }

            deserialize(
                data,
                key="request",
                content=flow.request.content,
                interface=interface,
                export_content_files_to=export_content_files_to,
            )

            if flow.error and flow.error.msg == FlowError.KILLED_MESSAGE:
                data["response"] = None
            else:
                deserialize(
                    data,
                    key="response",
                    content=flow.response.content,
                    interface=interface,
                    export_content_files_to=export_content_files_to,
                )

            try:
                data = self._scrub(data)
            except:
                logger.exception("Fail to scrub data")

            logger.info(f"    => Saving data as {log_filename}")

            with open(log_filename, "w", encoding="utf-8", opener=lambda path, flags: os.open(path, flags, 0o777)) as f:
                json.dump(data, f, indent=2, cls=ObjectDumpEncoder)

        except:
            logger.exception("Unexpected error")

    def _modify_response(self, flow):
        if self.request_is_from_tracer(flow.request):
            if self.rc_api_enabled:
                self._add_rc_capabilities_in_info_request(flow)

                if flow.request.path == "/v0.7/config":

                    # mimic the default response from the agent
                    flow.response.status_code = 200
                    flow.response.content = b"{}"
                    flow.response.headers["Content-Type"] = "application/json"

                    if self.rc_api_command is not None:
                        request_content = json.loads(flow.request.content)
                        logger.info("    => modifying rc response")
                        flow.response.content = self.rc_api_command

                    elif self.rc_api_sequential_commands is not None:
                        request_content = json.loads(flow.request.content)
                        runtime_id = request_content["client"]["client_tracer"]["runtime_id"]
                        nth_api_command = self.rc_api_runtime_ids_request_count[runtime_id]
                        response = self.rc_api_sequential_commands[nth_api_command]

                        logger.info(f"    => Modifying RC response for runtime ID {runtime_id}")
                        logger.info(f"    => Overwriting /v0.7/config response #{nth_api_command}")

                        flow.response.content = json.dumps(response).encode()
                        flow.response.headers["st-proxy-overwrite-rc-response"] = f"{nth_api_command}"

                        if nth_api_command + 1 < len(self.rc_api_sequential_commands):
                            self.rc_api_runtime_ids_request_count[runtime_id] = nth_api_command + 1

            if self.span_meta_structs_disabled:
                self._remove_meta_structs_support(flow)

            if self.span_events is not None:
                self._modify_span_events_flag(flow)

    def _remove_meta_structs_support(self, flow):
        if flow.request.path == "/info" and str(flow.response.status_code) == "200":
            c = json.loads(flow.response.content)
            if "span_meta_structs" in c:
                logger.info("    => Overwriting /info response to remove span_meta_structs field")
                c.pop("span_meta_structs")
                flow.response.content = json.dumps(c).encode()

    def _add_rc_capabilities_in_info_request(self, flow):
        if flow.request.path == "/info" and str(flow.response.status_code) == "200":
            c = json.loads(flow.response.content)

            if "/v0.7/config" not in c["endpoints"]:
                logger.info("    => Overwriting /info response to include /v0.7/config")
                c["endpoints"].append("/v0.7/config")
                flow.response.content = json.dumps(c).encode()

    def _modify_span_events_flag(self, flow):
        """Modify the agent flag that signals support for native span event serialization.
        There are three possible cases:
        - Not configured: agent's response is not modified, the real agent behavior is preserved
        - `true`: agent advertises support for native span events serialization
        - `false`: agent advertises that it does not support native span events serialization
        """
        if flow.request.path == "/info" and str(flow.response.status_code) == "200":
            c = json.loads(flow.response.content)
            c["span_events"] = self.span_events
            flow.response.content = json.dumps(c).encode()


def start_proxy() -> None:

    # the port is used to know the origin of the request
    modes = [
        f"regular@{PORT_DIRECT_INTERACTION}",  # RC payload API
        f"regular@{PORT_WEBLOG}",  # weblog
        f"regular@{PORT_NODEJS_BUDDY}",  # nodejs_buddy
        f"regular@{PORT_JAVA_BUDDY}",  # java_buddy
        f"regular@{PORT_RUBY_BUDDY}",  # ruby_buddy
        f"regular@{PORT_GOLANG_BUDDY}",  # golang_buddy
        f"regular@{PORT_PYTHON_BUDDY}",  # python_buddy
        f"regular@{PORT_AGENT}",  # agent
    ]

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    opts = options.Options(mode=modes, listen_host="0.0.0.0", confdir="utils/proxy/.mitmproxy")  # noqa: S104
    proxy = master.Master(opts, event_loop=loop)
    proxy.addons.add(*default_addons())
    proxy.addons.add(errorcheck.ErrorCheck())
    proxy.addons.add(_RequestLogger())
    loop.run_until_complete(proxy.run())


if __name__ == "__main__":
    start_proxy()
