import asyncio
from collections import defaultdict
import json
import logging
import os
from datetime import datetime

from mitmproxy import master, options
from mitmproxy.addons import errorcheck, default_addons
from mitmproxy.flow import Error as FlowError, Flow

import rc_debugger
from rc_mock import MOCKED_RESPONSES
from _deserializer import deserialize

# prevent permission issues on file created by the proxy when the host is linux
os.umask(0)

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
handler.setFormatter(logging.Formatter("%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s", "%H:%M:%S"))
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

SIMPLE_TYPES = (bool, int, float, type(None))


messages_counts = defaultdict(int)


class ObjectDumpEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, bytes):
            return str(o)
        return json.JSONEncoder.default(self, o)


class _RequestLogger:
    def __init__(self) -> None:
        self.dd_api_key = os.environ["DD_API_KEY"]
        self.dd_application_key = os.environ.get("DD_APPLICATION_KEY")
        self.dd_app_key = os.environ.get("DD_APP_KEY")
        self.state = json.loads(os.environ.get("PROXY_STATE", "{}"))
        self.host_log_folder = os.environ.get("SYSTEM_TESTS_HOST_LOG_FOLDER", "logs")

        # for config backend mock
        self.config_request_count = defaultdict(int)

        logger.debug(f"Proxy state: {self.state}")

        # request -> original port
        # as the port is overwritten at request stage, we loose it on response stage
        # this property will keep it

        self.original_ports = {}

    def _scrub(self, content):
        if isinstance(content, str):
            content = content.replace(self.dd_api_key, "{redacted-by-system-tests-proxy}")
            if self.dd_app_key:
                content = content.replace(self.dd_app_key, "{redacted-by-system-tests-proxy}")
            if self.dd_application_key:
                content = content.replace(self.dd_application_key, "{redacted-by-system-tests-proxy}")
            return content

        if isinstance(content, (list, set, tuple)):
            return [self._scrub(item) for item in content]

        if isinstance(content, dict):
            return {key: self._scrub(value) for key, value in content.items()}

        if isinstance(content, SIMPLE_TYPES):
            return content

        logger.error(f"Can't scrub type {type(content)}")
        return content

    def request(self, flow: Flow):

        logger.info(f"{flow.request.method} {flow.request.pretty_url}")

        self.original_ports[flow.id] = flow.request.port

        if flow.request.host in ("proxy", "localhost"):
            # tracer is the only container that uses the proxy directly

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
                elif otlp_path == "intake":
                    flow.request.host = "trace.agent." + os.environ.get("DD_SITE", "datad0g.com")
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

        try:
            logger.info(f"    => Response {flow.response.status_code}")

            self._modify_response(flow)

            # get the interface name
            if flow.request.headers.get("dd-protocol") == "otlp":
                interface = "open_telemetry"
            elif self.request_is_from_tracer(flow.request):
                port = self.original_ports[flow.id]
                if port == 8126:
                    interface = "library"
                elif port == 80:  # UDS mode
                    interface = "library"
                elif port == 9001:
                    interface = "python_buddy"
                elif port == 9002:
                    interface = "nodejs_buddy"
                elif port == 9003:
                    interface = "java_buddy"
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
            log_filename = f"{log_foldename}/{message_count:05d}_{path.replace('/', '_')}.json"

            data = {
                "log_filename": log_filename,
                "path": path,
                "query": query,
                "host": flow.request.host,
                "port": flow.request.port,
                "request": {
                    "timestamp_start": datetime.fromtimestamp(flow.request.timestamp_start).isoformat(),
                    "headers": list(flow.request.headers.items()),
                    "length": len(flow.request.content) if flow.request.content else 0,
                },
                "response": {
                    "status_code": flow.response.status_code,
                    "headers": list(flow.response.headers.items()),
                    "length": len(flow.response.content) if flow.response.content else 0,
                },
            }

            deserialize(data, key="request", content=flow.request.content, interface=interface)

            if flow.error and flow.error.msg == FlowError.KILLED_MESSAGE:
                data["response"] = None
            else:
                deserialize(data, key="response", content=flow.response.content, interface=interface)

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
        rc_config = self.state.get("mock_remote_config_backend")
        if rc_config is None:
            return
        mocked_responses = MOCKED_RESPONSES.get(rc_config)
        if mocked_responses is None:
            return
        self._modify_response_rc(flow, mocked_responses)

    def _modify_response_rc(self, flow, mocked_responses):
        if not self.request_is_from_tracer(flow.request):
            return  # modify only tracer/agent flow

        if flow.request.path == "/info" and str(flow.response.status_code) == "200":
            c = json.loads(flow.response.content)

            if "/v0.7/config" not in c["endpoints"]:
                logger.info("    => Overwriting /info response to include /v0.7/config")
                c["endpoints"].append("/v0.7/config")
                flow.response.content = json.dumps(c).encode()

        elif flow.request.path == "/v0.7/config":
            request_content = json.loads(flow.request.content)

            runtime_id = request_content["client"]["client_tracer"]["runtime_id"]
            logger.info(f"    => modifying rc response for runtime ID {runtime_id}")
            logger.info(f"    => Overwriting /v0.7/config response #{self.config_request_count[runtime_id] + 1}")

            if self.config_request_count[runtime_id] + 1 > len(mocked_responses):
                response = {}  # default content when there isn't an RC update
            else:
                if self.state.get("mock_remote_config_backend") in (
                    "DEBUGGER_PROBES_STATUS",
                    "DEBUGGER_LINE_PROBES_SNAPSHOT",
                    "DEBUGGER_METHOD_PROBES_SNAPSHOT",
                    "DEBUGGER_MIX_LOG_PROBE",
                ):
                    response = rc_debugger.create_rcm_probe_response(
                        request_content["client"]["client_tracer"]["language"],
                        mocked_responses[self.config_request_count[runtime_id]],
                        self.config_request_count[runtime_id],
                    )
                else:
                    response = mocked_responses[self.config_request_count[runtime_id]]

            flow.response.status_code = 200
            flow.response.content = json.dumps(response).encode()

            self.config_request_count[runtime_id] += 1


def start_proxy() -> None:

    # the port is used to make the distinction between weblogs (See CROSSED_TRACING_LIBRARIES scenario)
    modes = [
        "regular@8126",  # base weblog
        "regular@9001",  # python_buddy
        "regular@9002",  # nodejs_buddy
        "regular@9003",  # java_buddy
    ]

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    opts = options.Options(mode=modes, listen_host="0.0.0.0", confdir="utils/proxy/.mitmproxy")
    proxy = master.Master(opts, event_loop=loop)
    proxy.addons.add(*default_addons())
    proxy.addons.add(errorcheck.ErrorCheck())
    proxy.addons.add(_RequestLogger())
    loop.run_until_complete(proxy.run())


if __name__ == "__main__":
    start_proxy()
