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
    def execute(cls, flow, response_content):

        if cls.use_zombie_backend:
            logger.info("Zombie backend, kill response")
            flow.kill()


class Forwarder(object):
    def __init__(self):
        self.forward_ip = os.environ["FORWARD_TO_HOST"]
        self.forward_port = os.environ["FORWARD_TO_PORT"]
        self.interface_name = os.environ["INTERFACE_NAME"]

        logger.info("Forward flows to {}:{}".format(self.forward_ip, self.forward_port))

    def response(self, flow):
        logger.info(f"{flow.request.host}:{flow.request.port}{flow.request.path} {flow.response.status_code}")

        request_content = str(flow.request.content)
        response_content = str(flow.response.content)

        ProxyTrolls.execute(flow, response_content)

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
            logger.error("Can't resolve to forward to Host", self.forward_ip, self.forward_port)
        except ConnectionRefusedError:
            logger.error("Can't forward, connection refused")
        except BrokenPipeError:
            logger.error("Can't forward, broken pipe")
        except TimeoutError:
            logger.error("Can't forward, time out")
        except Exception as e:
            logger.error("Can't forward,", e)
        finally:
            conn.close()


logger.debug("Proxy trolls: " + os.environ.get("PROXY_TROLLS", ""))

addons = [Forwarder()]
