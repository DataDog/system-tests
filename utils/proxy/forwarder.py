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


logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
handler.setFormatter(logging.Formatter("%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s", "%H:%M:%S"))
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


class Forwarder(object):
    def __init__(self):
        self.forward_ip = os.environ.get("FORWARD_TO_HOST", "runner")
        self.forward_port = os.environ.get("FORWARD_TO_PORT", "8081")
        self.interface_name = os.environ.get("INTERFACE_NAME", "")

        # This is the proxy state. Basically, true or false values that tells the proxy to enable, or not
        # specific behavior. You can get/modify it using a direct GET/POST /_system_tests_state request to the proxy
        self.state = json.loads(os.environ.get("INITIAL_PROXY_STATE", "") or "{}")

        # for config backend mock
        self.config_request_count = 0

        logger.info(f"Initial state: {self.state}")
        logger.info(f"Forward flows to {self.forward_ip}:{self.forward_port}")

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
                "headers": self._scrub_headers(flow.request.headers),
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
                body=json.dumps(payload),
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

    @staticmethod
    def _scrub_headers(headers):
        result = []

        for key, value in headers.items():
            if key.lower() == "dd-api-key":
                value = "***"

            result.append((key, value))

        return result

    def _modify_response(self, flow):
        if self.state.get("mock_remote_config_backend"):

            if flow.request.path == "/v0.7/config" and str(flow.response.status_code) == "404":
                logger.info(f"Overwriting /v0.7/config response #{self.config_request_count + 1}")
                CONFIG_CONTENTS = [
                    b'{"targets":"eyJzaWduZWQiOnsiX3R5cGUiOiJ0YXJnZXRzIiwic3BlY192ZXJzaW9uIjoiMS4wIiwidmVyc2lvbiI6MiwiZXhwaXJlcyI6IjIwMjItMDgtMTBUMTk6NDk6MThaIiwidGFyZ2V0cyI6eyJkYXRhZG9nLzIvRkVBVFVSRVMvZGF0YWRvZy8yL0ZFQVRVUkVTL2ZlYXR1cmVzMS9jb25maWcvY29uZmlnIjp7Imxlbmd0aCI6MjUsImhhc2hlcyI6eyJzaGEyNTYiOiJlOTljYTQ0NjhkY2M4MzI5NTllODVjMmYxOTg0YjU2Y2RjNzhiNTIxMTdkNmM1Njk4YzI0ZDM1OWFhMDY5YzNhIn19LCJkYXRhZG9nLzIvTElWRV9ERUJVR0dJTkcvZGF0YWRvZy8yL0xJVkVfREVCVUdHSU5HL2xkMS9jb25maWcvY29uZmlnIjp7Imxlbmd0aCI6MjAwLCJoYXNoZXMiOnsic2hhMjU2IjoiZTg1NGQxMmI5OWNkMzIxYTAwZjllMDI4ZjY3NTUwYzczMjY2MTIxNmYyNDhkYTY5NTkxNTAyMjE4MDk0ZTBjMyJ9fX19LCJzaWduYXR1cmVzIjpbeyJrZXlpZCI6IjA3YmQ5ZGZlNmRjMzEzZWJhMmMwY2UxYzZhN2MxNjljMmI5MWMwOWY2OTNmNTc3ZGQwZmJkMzdhNGJlYzJkYTkiLCJzaWciOiJkZjkzNmJkMGZhYmJjMjYzZWE4MGYyM2MyYjhkZjA1Mjk0NWY0ZTZiOTU5NmZjYzkxYzJlZjBkMTUzMGFlM2Y2YmM4MjdlZDhmM2I2ZGNlZmMzZGUzYzkzZjQ0Mzg5ZmIyZDY3OTcyMTE0ZjFiZjM4YmMyYjE5YWVhOTFlMjgwNiJ9XX0=","target_files":[{"path":"features1","raw":"eyJhc20iOnsiZW5hYmxlZCI6dHJ1ZX19"},{"path":"ld1","raw":"eyJpZCI6InBldGNsaW5pYyIsIm9yZ0lkIjoyLCJzbmFwc2hvdFByb2JlcyI6W3siaWQiOiIyMjk1M2M4OC1lYWRjLTRmOWEtYWEwZi03ZjYyNDNmNGJmOGEiLCJ0eXBlIjoic25hcHNob3QiLCJjcmVhdGVkIjoxNjA1MDkzMDcxLCJsYW5ndWFnZSI6ImphdmEiLCJ0YWdzIjpbXSwiYWN0aXZlIjp0cnVlLCJ3aGVyZSI6eyJ0eXBlTmFtZSI6ImNvbS5kYXRhZG9nLlRhcmdldCIsIm1ldGhvZE5hbWUiOiJteU1ldGhvZCIsInNpZ25hdHVyZSI6ImphdmEubGFuZy5TdHJpbmcgKCkifX1dLCJtZXRyaWNQcm9iZXMiOlt7ImlkIjoiMzNhNjRkOTktZmJlZC01ZWFiLWJiMTAtODA3MzU0MDVjMDliIiwidHlwZSI6Im1ldHJpYyIsImNyZWF0ZWQiOjE2MDUwOTMwNzEsImxhbmd1YWdlIjoiamF2YSIsInRhZ3MiOltdLCJhY3RpdmUiOnRydWUsIndoZXJlIjp7InR5cGVOYW1lIjoiY29tLmRhdGFkb2cuVGFyZ2V0IiwibWV0aG9kTmFtZSI6Im15TWV0aG9kIiwic2lnbmF0dXJlIjoiamF2YS5sYW5nLlN0cmluZyAoKSJ9LCJraW5kIjoiQ09VTlQiLCJtZXRyaWNOYW1lIjoiZGF0YWRvZy5kZWJ1Z2dlci5jYWxscyIsInZhbHVlIjp7ImV4cHIiOiIjbG9jYWxWYXIxLmZpZWxkMS5maWVsZDIifX1dLCJhbGxvd0xpc3QiOnsicGFja2FnZVByZWZpeGVzIjpbImphdmEubGFuZyJdLCJjbGFzc2VzIjpbImphdmEubGFuZy51dGlsLk1hcCJdfSwiZGVueUxpc3QiOnsicGFja2FnZVByZWZpeGVzIjpbImphdmEuc2VjdXJpdHkiXSwiY2xhc3NlcyI6WyJqYXZheC5zZWN1cml0eS5hdXRoLkF1dGhQZXJtaXNzaW9uIl19LCJzYW1wbGluZyI6eyJzbmFwc2hvdHNQZXJTZWNvbmQiOjF9fQ=="}]}'
                    # TODO other payload
                ]

                if self.config_request_count + 1 > len(CONFIG_CONTENTS):
                    content = b'{"targets": None}'  # default content
                else:
                    content = CONFIG_CONTENTS[self.config_request_count]

                flow.response.status_code = 200
                flow.response.content = content

                self.config_request_count += 1


addons = [Forwarder()]
