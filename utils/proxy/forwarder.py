# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import os
import json
import socket
from datetime import datetime
from http.client import HTTPConnection
import logging
from mitmproxy import http
from mitmproxy.flow import Error as FlowError


SIMPLE_TYPES = (bool, int, float, type(None))

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
handler.setFormatter(logging.Formatter("%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s", "%H:%M:%S"))
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

with open("system-tests/utils/proxy/rc_mocked_responses_live_debugging.json") as f:
    RC_MOCKED_RESPONSES_LIVE_DEBUGGING = json.load(f)

with open("system-tests/utils/proxy/rc_mocked_responses_features.json") as f:
    RC_MOCKED_RESPONSES_FEATURES = json.load(f)

with open("system-tests/utils/proxy/rc_mocked_responses_asm_dd.json") as f:
    RC_MOCKED_RESPONSES_ASM_DD = json.load(f)

with open("system-tests/utils/proxy/rc_mocked_responses_live_debugging_nocache.json") as f:
    RC_MOCKED_RESPONSES_LIVE_DEBUGGING_NO_CACHE = json.load(f)

with open("system-tests/utils/proxy/rc_mocked_responses_features_nocache.json") as f:
    RC_MOCKED_RESPONSES_FEATURES_NO_CACHE = json.load(f)

with open("system-tests/utils/proxy/rc_mocked_responses_asm_dd_nocache.json") as f:
    RC_MOCKED_RESPONSES_ASM_DD_NO_CACHE = json.load(f)


class Forwarder(object):
    def __init__(self):
        self.forward_ip = os.environ.get("FORWARD_TO_HOST", "runner")
        self.forward_port = os.environ.get("FORWARD_TO_PORT", "8081")
        self.interface_name = os.environ.get("INTERFACE_NAME", "")

        self.dd_api_key = os.environ["DD_API_KEY"]

        # This is the proxy state. Basically, true or false values that tells the proxy to enable, or not
        # specific behavior. You can get/modify it using a direct GET/POST /_system_tests_state request to the proxy
        self.state = json.loads(os.environ.get("INITIAL_PROXY_STATE", "") or "{}")

        # for config backend mock
        self.config_request_count = 0

        logger.info(f"Initial state: {self.state}")
        logger.info(f"Forward flows to {self.forward_ip}:{self.forward_port}")

    def _scrub(self, content):
        if isinstance(content, str):
            return content.replace(self.dd_api_key, "{redacted-by-system-tests-proxy}")
        elif isinstance(content, (list, set, tuple)):
            return [self._scrub(item) for item in content]
        elif isinstance(content, dict):
            return {key: self._scrub(value) for key, value in content.items()}
        elif isinstance(content, SIMPLE_TYPES):
            return content
        else:
            logger.error(f"Can't scrub type {type(content)}")
            return content

    @staticmethod
    def is_direct_command(flow):
        return flow.request.path == "/_system_tests_state"

    @staticmethod
    def is_health_request(flow):
        return flow.request.path == "/_system_tests_health"

    def request(self, flow):
        if self.is_health_request(flow):
            flow.response = http.Response.make(200, "ok\n")

        if self.is_direct_command(flow):
            logger.info(f"Direct command to proxy: {flow.request.pretty_url}")

            try:
                if flow.request.method == "GET":
                    flow.response = http.Response.make(
                        200, json.dumps(self.state), {"Content-Type": "application/json"}
                    )

                elif flow.request.method == "POST":
                    new_state = json.loads(flow.request.content)
                    logger.info(f"New state: {new_state}")
                    self.state.clear()
                    self.state.update(new_state)
                    flow.response = http.Response.make(
                        200, json.dumps(self.state), {"Content-Type": "application/json"}
                    )
                else:
                    flow.response = http.Response.make(405)
            except Exception as e:
                flow.response = http.Response.make(500, repr(e))

    def response(self, flow):
        if self.is_direct_command(flow) or self.is_health_request(flow):
            return

        logger.info(f"Received {flow.request.pretty_url} {flow.response.status_code}")

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
                "headers": [(k, v) for k, v in flow.request.headers.items()],
                "length": len(flow.request.content) if flow.request.content else 0,
            },
            "response": {
                "status_code": flow.response.status_code,
                "content": response_content,
                "headers": [(k, v) for k, v in flow.response.headers.items()],
                "length": len(flow.response.content) if flow.response.content else 0,
            },
        }

        if flow.error and flow.error.msg == FlowError.KILLED_MESSAGE:
            payload["response"] = None

        conn = HTTPConnection(self.forward_ip, self.forward_port)

        try:
            conn.request(
                "POST",
                f"/proxy/{self.interface_name}",
                body=json.dumps(self._scrub(payload)),
                headers={"Content-type": "application/json"},
            )
        except socket.gaierror:
            logger.error(f"Can't resolve to forward {self.forward_ip}:{self.forward_port}")
        except ConnectionRefusedError:
            logger.error("Can't forward, connection refused")
        except BrokenPipeError:
            logger.error("Can't forward, broken pipe")
        except TimeoutError:
            logger.error("Can't forward, time out")
        except Exception as e:
            logger.error(f"Can't forward: {e}")
        finally:
            conn.close()

    def _modify_response(self, flow):
        if self.state.get("mock_remote_config_backend") == "FEATURES":
            self._modify_response_rc(flow, RC_MOCKED_RESPONSES_FEATURES)
        elif self.state.get("mock_remote_config_backend") == "LIVE_DEBUGGING":
            self._modify_response_rc(flow, RC_MOCKED_RESPONSES_LIVE_DEBUGGING)
        elif self.state.get("mock_remote_config_backend") == "ASM_DD":
            self._modify_response_rc(flow, RC_MOCKED_RESPONSES_ASM_DD)
        if self.state.get("mock_remote_config_backend") == "FEATURES_NO_CACHE":
            self._modify_response_rc(flow, RC_MOCKED_RESPONSES_FEATURES_NO_CACHE)
        elif self.state.get("mock_remote_config_backend") == "LIVE_DEBUGGING_NO_CACHE":
            self._modify_response_rc(flow, RC_MOCKED_RESPONSES_LIVE_DEBUGGING_NO_CACHE)
        elif self.state.get("mock_remote_config_backend") == "ASM_DD_NO_CACHE":
            self._modify_response_rc(flow, RC_MOCKED_RESPONSES_ASM_DD_NO_CACHE)

    def _modify_response_rc(self, flow, mocked_responses):
        logger.info("modifying rc response")
        if flow.request.path == "/v0.7/config" and str(flow.response.status_code) == "404":
            logger.info(f"Overwriting /v0.7/config response #{self.config_request_count + 1}")

            if self.config_request_count + 1 > len(mocked_responses):
                content = b"{}"  # default content when there isn't an RC update
            else:
                content = json.dumps(mocked_responses[self.config_request_count]).encode()

            flow.response.status_code = 200
            flow.response.content = content

            self.config_request_count += 1


addons = [Forwarder()]
