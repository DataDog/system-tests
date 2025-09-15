# keep this import in first
import scrubber  # noqa: F401

import asyncio
from collections import defaultdict
import json
import logging
import os
from typing import Any
from datetime import datetime, UTC

from mitmproxy import master, options, http
from mitmproxy.addons import errorcheck, default_addons
from mitmproxy.flow import Error as FlowError, Flow
from mitmproxy.http import HTTPFlow, Request

from _deserializer import deserialize
from ports import ProxyPorts

# prevent permission issues on file created by the proxy when the host is linux
os.umask(0)

logger = logging.getLogger(__name__)

SIMPLE_TYPES = (bool, int, float, type(None))

messages_counts: dict[str, int] = defaultdict(int)


class ObjectDumpEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:  # noqa: ANN401
        if isinstance(o, bytes):
            return str(o)
        return json.JSONEncoder.default(self, o)


class _RequestLogger:
    def __init__(self) -> None:
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(fmt="%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s", datefmt="%H:%M:%S")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        self.host_log_folder = os.environ.get("SYSTEM_TESTS_HOST_LOG_FOLDER", "logs")

        self.rc_api_enabled = os.environ.get("SYSTEM_TESTS_RC_API_ENABLED") == "True"
        self.mocked_backend = os.environ.get("SYSTEM_TESTS_SYSTEM_TEST_MOCKED_BACKEND") == "True"

        self.span_meta_structs_disabled = os.environ.get("SYSTEM_TESTS_AGENT_SPAN_META_STRUCTS_DISABLED") == "True"

        self.tracing_agent_target_host = os.environ.get("PROXY_TRACING_AGENT_TARGET_HOST", "agent")
        self.tracing_agent_target_port = int(os.environ.get("PROXY_TRACING_AGENT_TARGET_PORT", "8127"))

        span_events = os.environ.get("SYSTEM_TESTS_AGENT_SPAN_EVENTS")
        self.span_events = span_events != "False"

        self.rc_api_command = None

        # mimic the old API
        self.rc_api_sequential_commands = None
        self.rc_api_runtime_ids_request_count: dict = {}

    @staticmethod
    def get_error_response(message: bytes) -> http.Response:
        logger.error(message)
        return http.Response.make(400, message)

    def request(self, flow: HTTPFlow):
        # sockname is the local address (host, port) we received this connection on.
        port = flow.client_conn.sockname[1]

        logger.info(f"{flow.request.method} {flow.request.pretty_url}, using proxy port {port}")

        if port == ProxyPorts.proxy_commands:
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

        # if flow.request.headers.get("dd-protocol") == "otlp":
        if port == ProxyPorts.open_telemetry_weblog:
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
                raise ValueError(f"Unknown OTLP ingestion path {otlp_path}")

            logger.info(f"    => reverse proxy to {flow.request.pretty_url}")

        elif port in (
            ProxyPorts.python_buddy,
            ProxyPorts.nodejs_buddy,
            ProxyPorts.java_buddy,
            ProxyPorts.ruby_buddy,
            ProxyPorts.golang_buddy,
            ProxyPorts.weblog,
        ):
            flow.request.host, flow.request.port = (
                self.tracing_agent_target_host,
                self.tracing_agent_target_port,
            )
            flow.request.scheme = "http"
            logger.info(f"    => reverse proxy to {flow.request.pretty_url}")
        elif port == ProxyPorts.agent and self.mocked_backend:
            flow.response = http.Response.make(202, b"Ok")

    @staticmethod
    def request_is_from_tracer(request: Request) -> bool:
        return request.host == "agent"

    def response(self, flow: HTTPFlow):
        # sockname is the local address (host, port) we received this connection on.
        port = flow.client_conn.sockname[1]

        if port == ProxyPorts.proxy_commands:
            return

        try:
            logger.info(f"    => {flow.request.pretty_url} Response {flow.response.status_code}")

            self._modify_response(flow)

            # get the interface name
            if port == ProxyPorts.open_telemetry_weblog:
                interface = "open_telemetry"
            elif port == ProxyPorts.weblog:
                interface = "library"
            elif port == ProxyPorts.python_buddy:
                interface = "python_buddy"
            elif port == ProxyPorts.nodejs_buddy:
                interface = "nodejs_buddy"
            elif port == ProxyPorts.java_buddy:
                interface = "java_buddy"
            elif port == ProxyPorts.ruby_buddy:
                interface = "ruby_buddy"
            elif port == ProxyPorts.golang_buddy:
                interface = "golang_buddy"
            elif port == ProxyPorts.agent:  # HTTPS port, as the agent use the proxy with HTTP_PROXY env var
                interface = "agent"
            else:
                raise ValueError(f"Unknown port provenance for {flow.request}: {port}")

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

            logger.info(f"    => Saving {flow.request.pretty_url} as {log_filename}")

            with open(log_filename, "w", encoding="utf-8", opener=lambda path, flags: os.open(path, flags, 0o777)) as f:
                json.dump(data, f, indent=2, cls=ObjectDumpEncoder)

        except:
            logger.exception("Unexpected error")

    def _modify_response(self, flow: Flow):
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

            self._modify_span_events_flag(flow)

    def _remove_meta_structs_support(self, flow: Flow):
        if flow.request.path == "/info" and str(flow.response.status_code) == "200":
            c = json.loads(flow.response.content)
            if "span_meta_structs" in c:
                logger.info("    => Overwriting /info response to remove span_meta_structs field")
                c.pop("span_meta_structs")
                flow.response.content = json.dumps(c).encode()

    def _add_rc_capabilities_in_info_request(self, flow: Flow):
        if flow.request.path == "/info" and str(flow.response.status_code) == "200":
            c = json.loads(flow.response.content)

            if "/v0.7/config" not in c["endpoints"]:
                logger.info("    => Overwriting /info response to include /v0.7/config")
                c["endpoints"].append("/v0.7/config")
                flow.response.content = json.dumps(c).encode()

    def _modify_span_events_flag(self, flow: Flow):
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
    # the port is used to make the distinction between provenance
    # not that backend is not needed as it's used with HTTP_PROXY
    modes = [
        f"regular@{ProxyPorts.proxy_commands}",  # RC payload API
        f"regular@{ProxyPorts.weblog}",  # base weblog
        f"regular@{ProxyPorts.python_buddy}",  # python_buddy
        f"regular@{ProxyPorts.nodejs_buddy}",  # nodejs_buddy
        f"regular@{ProxyPorts.java_buddy}",  # java_buddy
        f"regular@{ProxyPorts.ruby_buddy}",  # ruby_buddy
        f"regular@{ProxyPorts.golang_buddy}",  # golang_buddy
        f"regular@{ProxyPorts.open_telemetry_weblog}",  # Open telemetry weblog
        f"regular@{ProxyPorts.agent}",  # from agent to backend
    ]

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    listen_host = "::" if os.environ.get("SYSTEM_TESTS_IPV6") == "True" else "0.0.0.0"  # noqa: S104
    opts = options.Options(mode=modes, listen_host=listen_host, confdir="utils/proxy/.mitmproxy")
    proxy = master.Master(opts, event_loop=loop)
    proxy.addons.add(*default_addons())
    proxy.addons.add(errorcheck.ErrorCheck())
    proxy.addons.add(_RequestLogger())
    loop.run_until_complete(proxy.run())


if __name__ == "__main__":
    start_proxy()
