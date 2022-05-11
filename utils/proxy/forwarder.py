# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import os
import json
import socket
from datetime import datetime
from http.client import HTTPConnection
import logging
from mitmproxy.flow import Error as FlowError


logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
handler.setFormatter(logging.Formatter("%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s", "%H:%M:%S"))
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

CONFIG_CONTENT = b'{"targets":"eyJzaWduZWQiOnsiX3R5cGUiOiJ0YXJnZXRzIiwic3BlY192ZXJzaW9uIjoiMS4wIiwidmVyc2lvbiI6MiwiZXhwaXJlcyI6IjIwMjItMDgtMTBUMTk6NDk6MThaIiwidGFyZ2V0cyI6eyJkYXRhZG9nLzIvRkVBVFVSRVMvZGF0YWRvZy8yL0ZFQVRVUkVTL2ZlYXR1cmVzMS9jb25maWcvY29uZmlnIjp7Imxlbmd0aCI6MjUsImhhc2hlcyI6eyJzaGEyNTYiOiJlOTljYTQ0NjhkY2M4MzI5NTllODVjMmYxOTg0YjU2Y2RjNzhiNTIxMTdkNmM1Njk4YzI0ZDM1OWFhMDY5YzNhIn19LCJkYXRhZG9nLzIvTElWRV9ERUJVR0dJTkcvZGF0YWRvZy8yL0xJVkVfREVCVUdHSU5HL2xkMS9jb25maWcvY29uZmlnIjp7Imxlbmd0aCI6MjAwLCJoYXNoZXMiOnsic2hhMjU2IjoiZTg1NGQxMmI5OWNkMzIxYTAwZjllMDI4ZjY3NTUwYzczMjY2MTIxNmYyNDhkYTY5NTkxNTAyMjE4MDk0ZTBjMyJ9fX19LCJzaWduYXR1cmVzIjpbeyJrZXlpZCI6IjA3YmQ5ZGZlNmRjMzEzZWJhMmMwY2UxYzZhN2MxNjljMmI5MWMwOWY2OTNmNTc3ZGQwZmJkMzdhNGJlYzJkYTkiLCJzaWciOiJkZjkzNmJkMGZhYmJjMjYzZWE4MGYyM2MyYjhkZjA1Mjk0NWY0ZTZiOTU5NmZjYzkxYzJlZjBkMTUzMGFlM2Y2YmM4MjdlZDhmM2I2ZGNlZmMzZGUzYzkzZjQ0Mzg5ZmIyZDY3OTcyMTE0ZjFiZjM4YmMyYjE5YWVhOTFlMjgwNiJ9XX0=","target_files":[{"path":"features1","raw":"eyJhc20iOnsiZW5hYmxlZCI6dHJ1ZX19"},{"path":"ld1","raw":"eyJpZCI6InBldGNsaW5pYyIsIm9yZ0lkIjoyLCJzbmFwc2hvdFByb2JlcyI6W3siaWQiOiIyMjk1M2M4OC1lYWRjLTRmOWEtYWEwZi03ZjYyNDNmNGJmOGEiLCJ0eXBlIjoic25hcHNob3QiLCJjcmVhdGVkIjoxNjA1MDkzMDcxLCJsYW5ndWFnZSI6ImphdmEiLCJ0YWdzIjpbXSwiYWN0aXZlIjp0cnVlLCJ3aGVyZSI6eyJ0eXBlTmFtZSI6ImNvbS5kYXRhZG9nLlRhcmdldCIsIm1ldGhvZE5hbWUiOiJteU1ldGhvZCIsInNpZ25hdHVyZSI6ImphdmEubGFuZy5TdHJpbmcgKCkifX1dLCJtZXRyaWNQcm9iZXMiOlt7ImlkIjoiMzNhNjRkOTktZmJlZC01ZWFiLWJiMTAtODA3MzU0MDVjMDliIiwidHlwZSI6Im1ldHJpYyIsImNyZWF0ZWQiOjE2MDUwOTMwNzEsImxhbmd1YWdlIjoiamF2YSIsInRhZ3MiOltdLCJhY3RpdmUiOnRydWUsIndoZXJlIjp7InR5cGVOYW1lIjoiY29tLmRhdGFkb2cuVGFyZ2V0IiwibWV0aG9kTmFtZSI6Im15TWV0aG9kIiwic2lnbmF0dXJlIjoiamF2YS5sYW5nLlN0cmluZyAoKSJ9LCJraW5kIjoiQ09VTlQiLCJtZXRyaWNOYW1lIjoiZGF0YWRvZy5kZWJ1Z2dlci5jYWxscyIsInZhbHVlIjp7ImV4cHIiOiIjbG9jYWxWYXIxLmZpZWxkMS5maWVsZDIifX1dLCJhbGxvd0xpc3QiOnsicGFja2FnZVByZWZpeGVzIjpbImphdmEubGFuZyJdLCJjbGFzc2VzIjpbImphdmEubGFuZy51dGlsLk1hcCJdfSwiZGVueUxpc3QiOnsicGFja2FnZVByZWZpeGVzIjpbImphdmEuc2VjdXJpdHkiXSwiY2xhc3NlcyI6WyJqYXZheC5zZWN1cml0eS5hdXRoLkF1dGhQZXJtaXNzaW9uIl19LCJzYW1wbGluZyI6eyJzbmFwc2hvdHNQZXJTZWNvbmQiOjF9fQ=="}]}'


def _scrub_headers(headers):
    result = []

    for key, value in headers.items():
        if key.lower() == "dd-api-key":
            value = "***"

        result.append((key, value))

    return result


class ProxyTrolls:
    use_zombie_backend = "zombie_backend" in os.environ.get("PROXY_TROLLS", "")

    @classmethod
    def execute(cls, flow):

        if cls.use_zombie_backend:
            logger.info("Zombie backend, kill response")
            flow.kill()

        # mock a working backend/agent by overwriting
        if flow.request.path == "/v0.7/config" and str(flow.response.status_code) == "404":
            logger.info(f"Overwriting /v0.7/config response")
            flow.response.status_code = 200
            flow.response.content = CONFIG_CONTENT


class Forwarder(object):
    def __init__(self):
        self.forward_ip = os.environ["FORWARD_TO_HOST"]
        self.forward_port = os.environ["FORWARD_TO_PORT"]
        self.interface_name = os.environ["INTERFACE_NAME"]

        logger.info(f"Forward flows to {self.forward_ip}:{self.forward_port}")

    def response(self, flow):
        logger.info(f"Received {flow.request.host}:{flow.request.port}{flow.request.path} {flow.response.status_code}")

        ProxyTrolls.execute(flow)

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
                "headers": _scrub_headers(flow.request.headers),
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


logger.debug("Proxy trolls: " + os.environ.get("PROXY_TROLLS", ""))

addons = [Forwarder()]
