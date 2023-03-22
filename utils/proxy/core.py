import asyncio
from collections import defaultdict
import json
import os
import threading
import platform
from datetime import datetime

from mitmproxy import master, options
from mitmproxy.addons import errorcheck, default_addons
from mitmproxy.flow import Error as FlowError

from utils import interfaces
from utils.tools import logger

SIMPLE_TYPES = (bool, int, float, type(None))


BACKEND_LOCAL_PORT = 11111


with open("utils/proxy/rc_mocked_responses_live_debugging.json", encoding="utf-8") as f:
    RC_MOCKED_RESPONSES_LIVE_DEBUGGING = json.load(f)

with open("utils/proxy/rc_mocked_responses_asm_features.json", encoding="utf-8") as f:
    RC_MOCKED_RESPONSES_ASM_FEATURES = json.load(f)

with open("utils/proxy/rc_mocked_responses_asm_activate_only.json", encoding="utf-8") as f:
    RC_MOCKED_RESPONSES_ASM_ACTIVATE_ONLY = json.load(f)

with open("utils/proxy/rc_mocked_responses_asm_dd.json", encoding="utf-8") as f:
    RC_MOCKED_RESPONSES_ASM_DD = json.load(f)

with open("utils/proxy/rc_mocked_responses_asm_data.json", encoding="utf-8") as f:
    RC_MOCKED_RESPONSES_ASM_DATA = json.load(f)

with open("utils/proxy/rc_mocked_responses_asm.json", encoding="utf-8") as f:
    RC_MOCKED_RESPONSES_ASM = json.load(f)

with open("utils/proxy/rc_mocked_responses_live_debugging_nocache.json", encoding="utf-8") as f:
    RC_MOCKED_RESPONSES_LIVE_DEBUGGING_NO_CACHE = json.load(f)

with open("utils/proxy/rc_mocked_responses_asm_features_nocache.json", encoding="utf-8") as f:
    RC_MOCKED_RESPONSES_ASM_FEATURES_NO_CACHE = json.load(f)

with open("utils/proxy/rc_mocked_responses_asm_dd_nocache.json", encoding="utf-8") as f:
    RC_MOCKED_RESPONSES_ASM_DD_NO_CACHE = json.load(f)

with open("utils/proxy/rc_mocked_responses_asm_nocache.json", encoding="utf-8") as f:
    RC_MOCKED_RESPONSES_ASM_NO_CACHE = json.load(f)


class _RequestLogger:
    def __init__(self, state) -> None:
        self.dd_api_key = os.environ["DD_API_KEY"]
        self.dd_application_key = os.environ.get("DD_APPLICATION_KEY")
        self.dd_app_key = os.environ.get("DD_APP_KEY")
        self.state = state

        # for config backend mock
        self.config_request_count = defaultdict(int)

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

    def request(self, flow):
        # localhost because on UDS mode, UDS socket is redirected
        if flow.request.host in ("runner", "localhost", "host.docker.internal", "host-gateway"):
            flow.request.host, flow.request.port = "localhost", 8127
            flow.request.scheme = "http"

    @staticmethod
    def request_is_from_tracer(request):
        # as now, only the tracer use the proxy as a reverse proxy
        return request.host == "localhost"

    def response(self, flow):
        self._modify_response(flow)

        request_content = str(flow.request.content)
        response_content = str(flow.response.content)

        if "?" in flow.request.path:
            path, query = flow.request.path.split("?", 1)
        else:
            path, query = flow.request.path, ""

        payload = {
            "path": path,
            "query": query,
            "host": flow.request.host,
            "port": flow.request.port,
            "request": {
                "timestamp_start": datetime.fromtimestamp(flow.request.timestamp_start).isoformat(),
                "content": request_content,
                "headers": list(flow.request.headers.items()),
                "length": len(flow.request.content) if flow.request.content else 0,
            },
            "response": {
                "status_code": flow.response.status_code,
                "content": response_content,
                "headers": list(flow.response.headers.items()),
                "length": len(flow.response.content) if flow.response.content else 0,
            },
        }

        if flow.error and flow.error.msg == FlowError.KILLED_MESSAGE:
            payload["response"] = None

        dd_site_url = get_dd_site_api_host()

        if self.request_is_from_tracer(flow.request):
            interface = interfaces.library
        elif f"https://{flow.request.host}" == dd_site_url:
            interface = interfaces.backend
        else:
            interface = interfaces.agent

        try:
            interface.append_data(self._scrub(payload))
        except:
            logger.exception("Fail to send data to {interface}")

    def _modify_response(self, flow):
        if self.state.get("mock_remote_config_backend") == "ASM_FEATURES":
            self._modify_response_rc(flow, RC_MOCKED_RESPONSES_ASM_FEATURES)
        elif self.state.get("mock_remote_config_backend") == "ASM_ACTIVATE_ONLY":
            self._modify_response_rc(flow, RC_MOCKED_RESPONSES_ASM_ACTIVATE_ONLY)
        elif self.state.get("mock_remote_config_backend") == "LIVE_DEBUGGING":
            self._modify_response_rc(flow, RC_MOCKED_RESPONSES_LIVE_DEBUGGING)
        elif self.state.get("mock_remote_config_backend") == "ASM_DD":
            self._modify_response_rc(flow, RC_MOCKED_RESPONSES_ASM_DD)
        elif self.state.get("mock_remote_config_backend") == "ASM_DATA":
            self._modify_response_rc(flow, RC_MOCKED_RESPONSES_ASM_DATA)
        elif self.state.get("mock_remote_config_backend") == "ASM":
            self._modify_response_rc(flow, RC_MOCKED_RESPONSES_ASM)
        elif self.state.get("mock_remote_config_backend") == "ASM_FEATURES_NO_CACHE":
            self._modify_response_rc(flow, RC_MOCKED_RESPONSES_ASM_FEATURES_NO_CACHE)
        elif self.state.get("mock_remote_config_backend") == "LIVE_DEBUGGING_NO_CACHE":
            self._modify_response_rc(flow, RC_MOCKED_RESPONSES_LIVE_DEBUGGING_NO_CACHE)
        elif self.state.get("mock_remote_config_backend") == "ASM_DD_NO_CACHE":
            self._modify_response_rc(flow, RC_MOCKED_RESPONSES_ASM_DD_NO_CACHE)
        elif self.state.get("mock_remote_config_backend") == "ASM_NO_CACHE":
            self._modify_response_rc(flow, RC_MOCKED_RESPONSES_ASM_NO_CACHE)

    def _modify_response_rc(self, flow, mocked_responses):
        if not self.request_is_from_tracer(flow.request):
            return  # modify only tracer/agent flow

        if flow.request.path == "/info" and str(flow.response.status_code) == "200":
            logger.info("Overwriting /info response to include /v0.7/config")
            c = json.loads(flow.response.content)
            c["endpoints"].append("/v0.7/config")
            flow.response.content = json.dumps(c).encode()
        elif flow.request.path == "/v0.7/config" and str(flow.response.status_code) == "404":
            runtime_id = json.loads(flow.request.content)["client"]["client_tracer"]["runtime_id"]
            logger.info(f"modifying rc response for runtime ID {runtime_id}")

            logger.info(f"Overwriting /v0.7/config response #{self.config_request_count[runtime_id] + 1}")

            if self.config_request_count[runtime_id] + 1 > len(mocked_responses):
                content = b"{}"  # default content when there isn't an RC update
            else:
                content = json.dumps(mocked_responses[self.config_request_count[runtime_id]]).encode()

            flow.response.status_code = 200
            flow.response.content = content

            self.config_request_count[runtime_id] += 1


def _start_background_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()


def start_proxy(state) -> None:
    loop = asyncio.new_event_loop()

    thread = threading.Thread(target=_start_background_loop, args=(loop,), daemon=True)
    thread.start()

    dd_site_url = get_dd_site_api_host()
    modes = [
        # Used for tracer/agents
        "regular",
        # Used for the interaction with the backend API
        f"reverse:{dd_site_url}@{BACKEND_LOCAL_PORT}",
    ]

    if platform.system() == "Darwin":
        listen_host = "127.0.0.1"  # on mac, we can listen only localhost, and it saves a click
    else:
        listen_host = "0.0.0.0"

    opts = options.Options(mode=modes, listen_host=listen_host, listen_port=8126, confdir="utils/proxy/.mitmproxy")

    proxy = master.Master(opts, event_loop=loop)
    proxy.addons.add(*default_addons())
    # proxy.addons.add(keepserving.KeepServing())
    proxy.addons.add(errorcheck.ErrorCheck())
    proxy.addons.add(_RequestLogger(state or {}))

    asyncio.run_coroutine_threadsafe(proxy.run(), loop)


def get_dd_site_api_host():
    # https://docs.datadoghq.com/getting_started/site/#access-the-datadog-site
    # DD_SITE => API HOST
    # datad0g.com       => dd.datad0g.com
    # datadoghq.com     => app.datadoghq.com
    # datadoghq.eu      => app.datadoghq.eu
    # ddog-gov.com      => app.ddog-gov.com
    # XYZ.datadoghq.com => XYZ.datadoghq.com

    dd_site = os.environ.get("DD_SITE", "datad0g.com")
    dd_site_to_app = {
        "datad0g.com": "https://dd.datad0g.com",
        "datadoghq.com": "https://app.datadoghq.com",
        "datadoghq.eu": "https://app.datadoghq.eu",
        "ddog-gov.com": "https://app.ddog-gov.com",
        "us3.datadoghq.com": "https://us3.datadoghq.com",
        "us5.datadoghq.com": "https://us5.datadoghq.com",
    }
    dd_app_url = dd_site_to_app.get(dd_site)
    assert dd_app_url is not None, f"We could not resolve a proper Datadog API URL given DD_SITE[{dd_site}]!"

    logger.debug(f"Using Datadog API URL[{dd_app_url}] as resolved from DD_SITE[{dd_site}].")
    return dd_app_url


if __name__ == "__main__":

    import time

    start_proxy(None)
    time.sleep(1000)
