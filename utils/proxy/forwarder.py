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
        self.state = json.loads(os.environ.get("INITIAL_PROXY_STATE", "") or '{"mock_remote_config_backend": true}')

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
                    b'{"targets":"eyJzaWduZWQiOnsiX3R5cGUiOiJ0YXJnZXRzIiwic3BlY192ZXJzaW9uIjoiMS4wIiwidmVyc2lvbiI6MSwiZXhwaXJlcyI6IjIwMjItMDktMTNUMTc6Mzk6NDFaIiwidGFyZ2V0cyI6e319LCJzaWduYXR1cmVzIjpbeyJrZXlpZCI6ImVkNzY3MmM5YTI0YWJkYTc4ODcyZWUzMmVlNzFjN2NiMWQ1MjM1ZThkYjRlY2JmMWNhMjhiOWM1MGViNzVkOWUiLCJzaWciOiI4MmUyYWNlMmU5Yzk3ZDM4NjgyMWQwYmI0MzYxZDI2ODc5ZDJmMWJiNjA4ZjZhNDZjOWRlYjk0MmY2YjI2YmEzNTU4NDVhNmExZjdlZmE4YjU2OTE4ODZmN2NjODQ0MWIxMmQwZTFjNTQ3YmExMGFhNzU5N2UxZGUyMmIyYmYwMyJ9XX0="}',
                    b'{"targets":"eyJzaWduZWQiOnsiX3R5cGUiOiJ0YXJnZXRzIiwic3BlY192ZXJzaW9uIjoiMS4wIiwidmVyc2lvbiI6MiwiZXhwaXJlcyI6IjIwMjItMDktMTNUMTc6Mzk6NDFaIiwidGFyZ2V0cyI6eyJkYXRhZG9nLzIvQVNNX0REL2FzbWRkMS9jb25maWciOnsibGVuZ3RoIjozLCJoYXNoZXMiOnsic2hhMjU2IjoiMmMyNmI0NmI2OGZmYzY4ZmY5OWI0NTNjMWQzMDQxMzQxMzQyMmQ3MDY0ODNiZmEwZjk4YTVlODg2MjY2ZTdhZSJ9LCJjdXN0b20iOnsidiI6MX19fX0sInNpZ25hdHVyZXMiOlt7ImtleWlkIjoiZWQ3NjcyYzlhMjRhYmRhNzg4NzJlZTMyZWU3MWM3Y2IxZDUyMzVlOGRiNGVjYmYxY2EyOGI5YzUwZWI3NWQ5ZSIsInNpZyI6IjRiZmIxMjA5ODllYzFmNTNhOGZhYmE4ZjdhMWY5MmU5N2UwN2VjOWU1MGQ2Mjk3Y2E1YzU2MDA5Mjg4MjEzNDEzZGJjNTIxMTA4OTIxNWIyN2JlYzE3MTZmMGExNzhlYjJkZGFmMjYxMGM0ZjM5MjQ5YTJjY2Q3NmVmMzY3ZTBjIn1dfQ==","target_files":[{"path":"datadog/2/ASM_DD/asmdd1/config","raw":"Zm9v"}],"client_configs":["datadog/2/ASM_DD/asmdd1/config"]}',
                    b'{"targets":"eyJzaWduZWQiOnsiX3R5cGUiOiJ0YXJnZXRzIiwic3BlY192ZXJzaW9uIjoiMS4wIiwidmVyc2lvbiI6MywiZXhwaXJlcyI6IjIwMjItMDktMTNUMTc6Mzk6NDFaIiwidGFyZ2V0cyI6eyJkYXRhZG9nLzIvQVNNX0REL2FzbWRkMS9jb25maWciOnsibGVuZ3RoIjozLCJoYXNoZXMiOnsic2hhMjU2IjoiMmMyNmI0NmI2OGZmYzY4ZmY5OWI0NTNjMWQzMDQxMzQxMzQyMmQ3MDY0ODNiZmEwZjk4YTVlODg2MjY2ZTdhZSJ9LCJjdXN0b20iOnsidiI6MX19LCJkYXRhZG9nLzIvRkVBVFVSRVMvZmVhdHVyZXMxL2NvbmZpZyI6eyJsZW5ndGgiOjI1LCJoYXNoZXMiOnsic2hhMjU2IjoiZTk5Y2E0NDY4ZGNjODMyOTU5ZTg1YzJmMTk4NGI1NmNkYzc4YjUyMTE3ZDZjNTY5OGMyNGQzNTlhYTA2OWMzYSJ9LCJjdXN0b20iOnsidiI6MX19fX0sInNpZ25hdHVyZXMiOlt7ImtleWlkIjoiZWQ3NjcyYzlhMjRhYmRhNzg4NzJlZTMyZWU3MWM3Y2IxZDUyMzVlOGRiNGVjYmYxY2EyOGI5YzUwZWI3NWQ5ZSIsInNpZyI6ImZiYjQ4MTFjMzVlNjA5MzNjNDYwYzYzZmQ4M2Y1ZDNmNTU2MGI2MDgyZGM1MTkzZGM0ZGY3ZjI5YzU0OWM5MGZlZDE0ODZlYjBkMjdjZWQ0MDg3MzJjYmYxNjExYWMwYWM4ZjI4YTU2YzdkNDAyZGFkY2VjNWZkNDg0ZTc0YTAzIn1dfQ==","target_files":[{"path":"datadog/2/FEATURES/features1/config","raw":"eyJhc20iOnsiZW5hYmxlZCI6ZmFsc2V9fQ=="}],"client_configs":["datadog/2/ASM_DD/asmdd1/config","datadog/2/FEATURES/features1/config"]}',
                    b'{"targets":"eyJzaWduZWQiOnsiX3R5cGUiOiJ0YXJnZXRzIiwic3BlY192ZXJzaW9uIjoiMS4wIiwidmVyc2lvbiI6NCwiZXhwaXJlcyI6IjIwMjItMDktMTNUMTc6Mzk6NDFaIiwidGFyZ2V0cyI6eyJkYXRhZG9nLzIvQVNNX0REL2FzbWRkMS9jb25maWciOnsibGVuZ3RoIjozLCJoYXNoZXMiOnsic2hhMjU2IjoiZmNkZTJiMmVkYmE1NmJmNDA4NjAxZmI3MjFmZTliNWMzMzhkMTBlZTQyOWVhMDRmYWU1NTExYjY4ZmJmOGZiOSJ9LCJjdXN0b20iOnsidiI6Mn19LCJkYXRhZG9nLzIvRkVBVFVSRVMvZmVhdHVyZXMxL2NvbmZpZyI6eyJsZW5ndGgiOjI1LCJoYXNoZXMiOnsic2hhMjU2IjoiZTk5Y2E0NDY4ZGNjODMyOTU5ZTg1YzJmMTk4NGI1NmNkYzc4YjUyMTE3ZDZjNTY5OGMyNGQzNTlhYTA2OWMzYSJ9LCJjdXN0b20iOnsidiI6MX19fX0sInNpZ25hdHVyZXMiOlt7ImtleWlkIjoiZWQ3NjcyYzlhMjRhYmRhNzg4NzJlZTMyZWU3MWM3Y2IxZDUyMzVlOGRiNGVjYmYxY2EyOGI5YzUwZWI3NWQ5ZSIsInNpZyI6IjNkZjBmNjE1ZDdmNzk2Y2RkYWNkNGE2Y2VlODdhZWYxYzI5ZWRjNDFjMDNhZTBjMTkwMGI3ODRkNDlkMTRhZGRjN2ZkYzRmODUzYmUyYTNiMTY5NDQxYWFhN2Y0ZDkxMmI4OGU1MjAyMWU0NjdhNzZmYWQ0ZTk0MDgwYWU4NTAwIn1dfQ==","target_files":[{"path":"datadog/2/ASM_DD/asmdd1/config","raw":"YmFy"}],"client_configs":["datadog/2/ASM_DD/asmdd1/config","datadog/2/FEATURES/features1/config"]}',
                    b'{"targets":"eyJzaWduZWQiOnsiX3R5cGUiOiJ0YXJnZXRzIiwic3BlY192ZXJzaW9uIjoiMS4wIiwidmVyc2lvbiI6NSwiZXhwaXJlcyI6IjIwMjItMDktMTNUMTc6Mzk6NDFaIiwidGFyZ2V0cyI6eyJkYXRhZG9nLzIvRkVBVFVSRVMvZmVhdHVyZXMxL2NvbmZpZyI6eyJsZW5ndGgiOjI1LCJoYXNoZXMiOnsic2hhMjU2IjoiZTk5Y2E0NDY4ZGNjODMyOTU5ZTg1YzJmMTk4NGI1NmNkYzc4YjUyMTE3ZDZjNTY5OGMyNGQzNTlhYTA2OWMzYSJ9LCJjdXN0b20iOnsidiI6MX19LCJkYXRhZG9nLzIvRkVBVFVSRVMvZmVhdHVyZXMyL2NvbmZpZyI6eyJsZW5ndGgiOjI0LCJoYXNoZXMiOnsic2hhMjU2IjoiMDE1OTY1OGFiODViZTcyMDc3NjFhNDExMTE3MmIwMTU1ODM5NGJmYzc0YTFmZTFkMzE0ZjIwMjNmN2M2NTZkYiJ9LCJjdXN0b20iOnsidiI6MX19fX0sInNpZ25hdHVyZXMiOlt7ImtleWlkIjoiZWQ3NjcyYzlhMjRhYmRhNzg4NzJlZTMyZWU3MWM3Y2IxZDUyMzVlOGRiNGVjYmYxY2EyOGI5YzUwZWI3NWQ5ZSIsInNpZyI6IjliYTVlNjU1MzliNzhkMmUyYjRiZDc3Y2M5MjEzZjdmOGEzMGVhYjg1MWE0YzVjMzc5MDkwMjQxYzE1MDNkZWE1OWFmMjJhOTIyZWRiYmVlMzNhZDIyNTMxNzMyMTBjYTU2NjUzNTgwOWQzOWM0MmIyNTM5NGQ4MDE5Y2Y1ZjAwIn1dfQ==","target_files":[{"path":"datadog/2/FEATURES/features2/config","raw":"eyJhc20iOnsiZW5hYmxlZCI6dHJ1ZX19"}],"client_configs":["datadog/2/FEATURES/features1/config","datadog/2/FEATURES/features2/config"]}',
                    b'{"targets":"eyJzaWduZWQiOnsiX3R5cGUiOiJ0YXJnZXRzIiwic3BlY192ZXJzaW9uIjoiMS4wIiwidmVyc2lvbiI6NiwiZXhwaXJlcyI6IjIwMjItMDktMTNUMTc6Mzk6NDFaIiwidGFyZ2V0cyI6eyJkYXRhZG9nLzIvQVNNX0REL2FzbWRkMS9jb25maWciOnsibGVuZ3RoIjozLCJoYXNoZXMiOnsic2hhMjU2IjoiZmNkZTJiMmVkYmE1NmJmNDA4NjAxZmI3MjFmZTliNWMzMzhkMTBlZTQyOWVhMDRmYWU1NTExYjY4ZmJmOGZiOSJ9LCJjdXN0b20iOnsidiI6M319LCJkYXRhZG9nLzIvRkVBVFVSRVMvZmVhdHVyZXMxL2NvbmZpZyI6eyJsZW5ndGgiOjI0LCJoYXNoZXMiOnsic2hhMjU2IjoiMDE1OTY1OGFiODViZTcyMDc3NjFhNDExMTE3MmIwMTU1ODM5NGJmYzc0YTFmZTFkMzE0ZjIwMjNmN2M2NTZkYiJ9LCJjdXN0b20iOnsidiI6Mn19fX0sInNpZ25hdHVyZXMiOlt7ImtleWlkIjoiZWQ3NjcyYzlhMjRhYmRhNzg4NzJlZTMyZWU3MWM3Y2IxZDUyMzVlOGRiNGVjYmYxY2EyOGI5YzUwZWI3NWQ5ZSIsInNpZyI6ImZmMjYyNDllZThkOTg5N2ZmNDRlNjNjYzc5NjVhMjU2ZjIxZDdiMTAwOGYyOWRmZGVmZTNlNGE5ZTA3NmNmZTI0NTM3NjQzMjk1MGJjM2UwMjYyNzMwNjI1YzdhNGRjOWU1ODkyY2VjMWExZmJjOGQ5M2RmMTM2NmM3NzE0ZjAyIn1dfQ==","target_files":[{"path":"datadog/2/ASM_DD/asmdd1/config","raw":"YmFy"},{"path":"datadog/2/FEATURES/features1/config","raw":"eyJhc20iOnsiZW5hYmxlZCI6dHJ1ZX19"}],"client_configs":["datadog/2/FEATURES/features1/config","datadog/2/ASM_DD/asmdd1/config"]}',
                    b'{"targets":"eyJzaWduZWQiOnsiX3R5cGUiOiJ0YXJnZXRzIiwic3BlY192ZXJzaW9uIjoiMS4wIiwidmVyc2lvbiI6NywiZXhwaXJlcyI6IjIwMjItMDktMTNUMTc6Mzk6NDFaIiwidGFyZ2V0cyI6eyJkYXRhZG9nLzIvQVNNX0REL2FzbWRkMS9jb25maWciOnsibGVuZ3RoIjozLCJoYXNoZXMiOnsic2hhMjU2IjoiZmNkZTJiMmVkYmE1NmJmNDA4NjAxZmI3MjFmZTliNWMzMzhkMTBlZTQyOWVhMDRmYWU1NTExYjY4ZmJmOGZiOSJ9LCJjdXN0b20iOnsidiI6M319LCJkYXRhZG9nLzIvRkVBVFVSRVMvZmVhdHVyZXMxL2NvbmZpZyI6eyJsZW5ndGgiOjI0LCJoYXNoZXMiOnsic2hhMjU2IjoiMDE1OTY1OGFiODViZTcyMDc3NjFhNDExMTE3MmIwMTU1ODM5NGJmYzc0YTFmZTFkMzE0ZjIwMjNmN2M2NTZkYiJ9LCJjdXN0b20iOnsidiI6Mn19LCJkYXRhZG9nLzIvRkVBVFVSRVMvZmVhdHVyZXMzL2NvbmZpZyI6eyJsZW5ndGgiOjQ2LCJoYXNoZXMiOnsic2hhMjU2IjoiMTNhNzY5MmY2MjVmNTIyNTY0OGNjNmI2MjM4YzlmYmJkMjIwYmNiYjE1OTM3YTc0OTAxMWNkZjY1MjA1ZTIxMyJ9LCJjdXN0b20iOnsidiI6MX19fX0sInNpZ25hdHVyZXMiOlt7ImtleWlkIjoiZWQ3NjcyYzlhMjRhYmRhNzg4NzJlZTMyZWU3MWM3Y2IxZDUyMzVlOGRiNGVjYmYxY2EyOGI5YzUwZWI3NWQ5ZSIsInNpZyI6IjNlMDY1YjFjYTQ3ZGNhODRmNmVjMWUzNWJkN2JjMzczMDU0ODA3Mzg4MGEwYWJiMDkwYjg2NTFjYTI0MDhiNTk0ZWViNmM0OTAwZmU2YTkwMGNkYTI3YmMxZWUxOTYyNmZiMDA4ZjFjMGFmMjUxZGNlZDljZTExMTJkOWUyNzA1In1dfQ==","target_files":[{"path":"datadog/2/FEATURES/features3/config","raw":"eyJhc20iOnsiZW5hYmxlZCI6ZmFsc2V9LCJleHRyYSI6ImhlbGxvd29ybGQifQ=="}],"client_configs":["datadog/2/FEATURES/features1/config","datadog/2/FEATURES/features3/config","datadog/2/ASM_DD/asmdd1/config"]}',
                    b'{"targets":"eyJzaWduZWQiOnsiX3R5cGUiOiJ0YXJnZXRzIiwic3BlY192ZXJzaW9uIjoiMS4wIiwidmVyc2lvbiI6OCwiZXhwaXJlcyI6IjIwMjItMDktMTNUMTc6Mzk6NDFaIiwidGFyZ2V0cyI6eyJkYXRhZG9nLzIvQVNNX0REL2FzbWRkMS9jb25maWciOnsibGVuZ3RoIjozLCJoYXNoZXMiOnsic2hhMjU2IjoiZmNkZTJiMmVkYmE1NmJmNDA4NjAxZmI3MjFmZTliNWMzMzhkMTBlZTQyOWVhMDRmYWU1NTExYjY4ZmJmOGZiOSJ9LCJjdXN0b20iOnsidiI6M319LCJkYXRhZG9nLzIvQVNNX0REL2FzbWRkMy9jb25maWciOnsibGVuZ3RoIjo1LCJoYXNoZXMiOnsic2hhMjU2IjoiMmNmMjRkYmE1ZmIwYTMwZTI2ZTgzYjJhYzViOWUyOWUxYjE2MWU1YzFmYTc0MjVlNzMwNDMzNjI5MzhiOTgyNCJ9LCJjdXN0b20iOnsidiI6MX19LCJkYXRhZG9nLzIvRkVBVFVSRVMvZmVhdHVyZXMxL2NvbmZpZyI6eyJsZW5ndGgiOjI0LCJoYXNoZXMiOnsic2hhMjU2IjoiMDE1OTY1OGFiODViZTcyMDc3NjFhNDExMTE3MmIwMTU1ODM5NGJmYzc0YTFmZTFkMzE0ZjIwMjNmN2M2NTZkYiJ9LCJjdXN0b20iOnsidiI6Mn19LCJkYXRhZG9nLzIvRkVBVFVSRVMvZmVhdHVyZXMzL2NvbmZpZyI6eyJsZW5ndGgiOjQ2LCJoYXNoZXMiOnsic2hhMjU2IjoiMTNhNzY5MmY2MjVmNTIyNTY0OGNjNmI2MjM4YzlmYmJkMjIwYmNiYjE1OTM3YTc0OTAxMWNkZjY1MjA1ZTIxMyJ9LCJjdXN0b20iOnsidiI6MX19fX0sInNpZ25hdHVyZXMiOlt7ImtleWlkIjoiZWQ3NjcyYzlhMjRhYmRhNzg4NzJlZTMyZWU3MWM3Y2IxZDUyMzVlOGRiNGVjYmYxY2EyOGI5YzUwZWI3NWQ5ZSIsInNpZyI6IjkzMGZkN2NiZGUzNDZiYzM2MTMyNDBhZGE1MDliOWZlNzUwYTkyYTg4ZDJhNzgxYzY4M2Q2MGU0MmQ5M2E5YTY5M2MzNDI0YmE3NDgyYTI4ZDYyZTU4NTc5ODIzYTM4YmZmYWMxMDkzZDk0ZDIxMTIwZGUxOTc2MjRjMmI2MTA2In1dfQ==","client_configs":["datadog/2/ASM_DD/asmdd1/config","datadog/2/FEATURES/features1/config","datadog/2/FEATURES/features3/config","datadog/2/ASM_DD/asmdd3/config"]}',
                    b'{"targets":"eyJzaWduZWQiOnsiX3R5cGUiOiJ0YXJnZXRzIiwic3BlY192ZXJzaW9uIjoiMS4wIiwidmVyc2lvbiI6OCwiZXhwaXJlcyI6IjIwMjItMDktMTNUMTc6Mzk6NDFaIiwidGFyZ2V0cyI6eyJkYXRhZG9nLzIvQVNNX0REL2FzbWRkMS9jb25maWciOnsibGVuZ3RoIjozLCJoYXNoZXMiOnsic2hhMjU2IjoiZmNkZTJiMmVkYmE1NmJmNDA4NjAxZmI3MjFmZTliNWMzMzhkMTBlZTQyOWVhMDRmYWU1NTExYjY4ZmJmOGZiOSJ9LCJjdXN0b20iOnsidiI6M319LCJkYXRhZG9nLzIvRkVBVFVSRVMvZmVhdHVyZXMxL2NvbmZpZyI6eyJsZW5ndGgiOjI0LCJoYXNoZXMiOnsic2hhMjU2IjoiMDE1OTY1OGFiODViZTcyMDc3NjFhNDExMTE3MmIwMTU1ODM5NGJmYzc0YTFmZTFkMzE0ZjIwMjNmN2M2NTZkYiJ9LCJjdXN0b20iOnsidiI6Mn19LCJkYXRhZG9nLzIvRkVBVFVSRVMvZmVhdHVyZXMzL2NvbmZpZyI6eyJsZW5ndGgiOjQ2LCJoYXNoZXMiOnsic2hhMjU2IjoiMTNhNzY5MmY2MjVmNTIyNTY0OGNjNmI2MjM4YzlmYmJkMjIwYmNiYjE1OTM3YTc0OTAxMWNkZjY1MjA1ZTIxMyJ9LCJjdXN0b20iOnsidiI6MX19fX0sInNpZ25hdHVyZXMiOlt7ImtleWlkIjoiZWQ3NjcyYzlhMjRhYmRhNzg4NzJlZTMyZWU3MWM3Y2IxZDUyMzVlOGRiNGVjYmYxY2EyOGI5YzUwZWI3NWQ5ZSIsInNpZyI6IjM2ZjEyZGUzOWZlZDcxNmRiMDBiNDJiNmE2NzZmMmMyMWQyZTAwNmZkZWY3MWIwOTE0MzYxZTU3YjU0NDQ2OTY2MTUwNDM3OWU3N2NkYzNjZGU2N2YzNWI3MzgxNzgzMzBmZjYwMDY3NmJmMWM3NzJlZTcyZGUzY2Q4MmE4ZDBmIn1dfQ==","client_configs":["datadog/2/ASM_DD/asmdd1/config","datadog/2/FEATURES/features1/config","datadog/2/FEATURES/features3/config"]}',
                    b'{"targets":"eyJzaWduZWQiOnsiX3R5cGUiOiJ0YXJnZXRzIiwic3BlY192ZXJzaW9uIjoiMS4wIiwidmVyc2lvbiI6OSwiZXhwaXJlcyI6IjIwMjItMDktMTNUMTc6Mzk6NDFaIiwidGFyZ2V0cyI6eyJkYXRhZG9nLzIvQVNNX0REL2FzbWRkMS9jb25maWciOnsibGVuZ3RoIjozLCJoYXNoZXMiOnsic2hhMjU2IjoiZmNkZTJiMmVkYmE1NmJmNDA4NjAxZmI3MjFmZTliNWMzMzhkMTBlZTQyOWVhMDRmYWU1NTExYjY4ZmJmOGZiOSJ9LCJjdXN0b20iOnsidiI6M319LCJkYXRhZG9nLzIvQVNNX0REL2FzbWRkNC9jb25maWciOnsibGVuZ3RoIjo1LCJoYXNoZXMiOnsic2hhMjU2IjoiNDg2ZWE0NjIyNGQxYmI0ZmI2ODBmMzRmN2M5YWQ5NmE4ZjI0ZWM4OGJlNzNlYThlNWE2YzY1MjYwZTljYjhhNyJ9LCJjdXN0b20iOnsidiI6MX19LCJkYXRhZG9nLzIvRkVBVFVSRVMvZmVhdHVyZXMxL2NvbmZpZyI6eyJsZW5ndGgiOjI0LCJoYXNoZXMiOnsic2hhMjU2IjoiMDE1OTY1OGFiODViZTcyMDc3NjFhNDExMTE3MmIwMTU1ODM5NGJmYzc0YTFmZTFkMzE0ZjIwMjNmN2M2NTZkYiJ9LCJjdXN0b20iOnsidiI6Mn19LCJkYXRhZG9nLzIvRkVBVFVSRVMvZmVhdHVyZXMzL2NvbmZpZyI6eyJsZW5ndGgiOjQ2LCJoYXNoZXMiOnsic2hhMjU2IjoiMTNhNzY5MmY2MjVmNTIyNTY0OGNjNmI2MjM4YzlmYmJkMjIwYmNiYjE1OTM3YTc0OTAxMWNkZjY1MjA1ZTIxMyJ9LCJjdXN0b20iOnsidiI6MX19fX0sInNpZ25hdHVyZXMiOlt7ImtleWlkIjoiZWQ3NjcyYzlhMjRhYmRhNzg4NzJlZTMyZWU3MWM3Y2IxZDUyMzVlOGRiNGVjYmYxY2EyOGI5YzUwZWI3NWQ5ZSIsInNpZyI6IjA2YmEwZDVhNDkyN2FkOWQ5YmM3YjI0ZTYxNjAyMDNkYWQ5NWQxMzYxNDEzOTUxMTM3NmY3Y2MzYzExNDYzNTYyNTYyZjY5ZWNmODE3NjY5ZWMxYzkyOGQxOWU0YWRhOGZkZjhiYjUzYWVmMTE4Yjc1Mzk0MTZmYTc5MGZlNTAzIn1dfQ==","target_files":[{"path":"datadog/2/ASM_DD/asmdd4/config","raw":"d29ybGQ="},{"path":"thisshouldbeignored","raw":"ImFXZHViM0psYldVPSI="}],"client_configs":["datadog/2/FEATURES/features1/config","datadog/2/FEATURES/features3/config","datadog/2/ASM_DD/asmdd4/config","datadog/2/ASM_DD/asmdd1/config"]}',
                    b'{"targets":"eyJzaWduZWQiOnsiX3R5cGUiOiJ0YXJnZXRzIiwic3BlY192ZXJzaW9uIjoiMS4wIiwidmVyc2lvbiI6MTAsImV4cGlyZXMiOiIyMDIyLTA5LTEzVDE3OjM5OjQxWiIsInRhcmdldHMiOnsiZGF0YWRvZy8yL0FTTV9ERC9hc21kZDEvY29uZmlnIjp7Imxlbmd0aCI6MywiaGFzaGVzIjp7InNoYTI1NiI6ImZjZGUyYjJlZGJhNTZiZjQwODYwMWZiNzIxZmU5YjVjMzM4ZDEwZWU0MjllYTA0ZmFlNTUxMWI2OGZiZjhmYjkifSwiY3VzdG9tIjp7InYiOjN9fSwiZGF0YWRvZy8yL0FTTV9ERC9hc21kZDQvY29uZmlnIjp7Imxlbmd0aCI6NSwiaGFzaGVzIjp7InNoYTI1NiI6IjQ4NmVhNDYyMjRkMWJiNGZiNjgwZjM0ZjdjOWFkOTZhOGYyNGVjODhiZTczZWE4ZTVhNmM2NTI2MGU5Y2I4YTcifSwiY3VzdG9tIjp7InYiOjF9fSwiZGF0YWRvZy8yL0FTTV9ERC90aGlzc2hvdWxkYWxzb2JlaWdub3JlZC9jb25maWciOnsibGVuZ3RoIjoxOCwiaGFzaGVzIjp7InNoYTI1NiI6IjkyZTk2MjkzNWUzZWFkZGJiNDRlYzI1ODkyZGExZjYyNzUyZGNmMjRjNjQwNTY5OTk1MzhkNTZhMDY5YTVhMmIifSwiY3VzdG9tIjp7InYiOjF9fSwiZGF0YWRvZy8yL0ZFQVRVUkVTL2ZlYXR1cmVzMS9jb25maWciOnsibGVuZ3RoIjoyNCwiaGFzaGVzIjp7InNoYTI1NiI6IjAxNTk2NThhYjg1YmU3MjA3NzYxYTQxMTExNzJiMDE1NTgzOTRiZmM3NGExZmUxZDMxNGYyMDIzZjdjNjU2ZGIifSwiY3VzdG9tIjp7InYiOjJ9fSwiZGF0YWRvZy8yL0ZFQVRVUkVTL2ZlYXR1cmVzMy9jb25maWciOnsibGVuZ3RoIjo0NiwiaGFzaGVzIjp7InNoYTI1NiI6IjEzYTc2OTJmNjI1ZjUyMjU2NDhjYzZiNjIzOGM5ZmJiZDIyMGJjYmIxNTkzN2E3NDkwMTFjZGY2NTIwNWUyMTMifSwiY3VzdG9tIjp7InYiOjF9fX19LCJzaWduYXR1cmVzIjpbeyJrZXlpZCI6ImVkNzY3MmM5YTI0YWJkYTc4ODcyZWUzMmVlNzFjN2NiMWQ1MjM1ZThkYjRlY2JmMWNhMjhiOWM1MGViNzVkOWUiLCJzaWciOiI2MDdkZmY1OGZjNzc2OTgyMGI2ZWUxNTBmMWE4MjI2Y2U4OWY3YmU1ZjMyM2ZkNWU0NDkzYzkzZDAxMWVlMjU1NjliNWQ1ZmIxYmI0Y2ExMDRkOTBmMGE2OTg4YWEwZjVmNjI0Yzc5YTBhNmNiMzQ4YzA4NDcyODBlMzEzMTgwOSJ9XX0=","client_configs":["datadog/2/ASM_DD/asmdd1/config","datadog/2/FEATURES/features1/config","datadog/2/FEATURES/features3/config","datadog/2/ASM_DD/asmdd4/config"]}',
                    b'{"targets":"eyJzaWduZWQiOnsiX3R5cGUiOiJ0YXJnZXRzIiwic3BlY192ZXJzaW9uIjoiMS4wIiwidmVyc2lvbiI6MTEsImV4cGlyZXMiOiIyMDIyLTA5LTEzVDE3OjM5OjQxWiIsInRhcmdldHMiOnsiZGF0YWRvZy8yL0FTTV9ERC9hc21kZDEvY29uZmlnIjp7Imxlbmd0aCI6MywiaGFzaGVzIjp7InNoYTI1NiI6ImZjZGUyYjJlZGJhNTZiZjQwODYwMWZiNzIxZmU5YjVjMzM4ZDEwZWU0MjllYTA0ZmFlNTUxMWI2OGZiZjhmYjkifSwiY3VzdG9tIjp7InYiOjN9fSwiZGF0YWRvZy8yL0FTTV9ERC9hc21kZDQvY29uZmlnIjp7Imxlbmd0aCI6NSwiaGFzaGVzIjp7InNoYTI1NiI6IjQ4NmVhNDYyMjRkMWJiNGZiNjgwZjM0ZjdjOWFkOTZhOGYyNGVjODhiZTczZWE4ZTVhNmM2NTI2MGU5Y2I4YTcifSwiY3VzdG9tIjp7InYiOjF9fSwiZGF0YWRvZy8yL0FTTV9ERC90aGlzc2hvdWxkYWxzb2JlaWdub3JlZC9jb25maWciOnsibGVuZ3RoIjoxOCwiaGFzaGVzIjp7InNoYTI1NiI6IjkyZTk2MjkzNWUzZWFkZGJiNDRlYzI1ODkyZGExZjYyNzUyZGNmMjRjNjQwNTY5OTk1MzhkNTZhMDY5YTVhMmIifSwiY3VzdG9tIjp7InYiOjF9fSwiZGF0YWRvZy8yL0ZFQVRVUkVTL2ZlYXR1cmVzMS9jb25maWciOnsibGVuZ3RoIjoyNCwiaGFzaGVzIjp7InNoYTI1NiI6IjAxNTk2NThhYjg1YmU3MjA3NzYxYTQxMTExNzJiMDE1NTgzOTRiZmM3NGExZmUxZDMxNGYyMDIzZjdjNjU2ZGIifSwiY3VzdG9tIjp7InYiOjJ9fSwiZGF0YWRvZy8yL0ZFQVRVUkVTL2ZlYXR1cmVzMy9jb25maWciOnsibGVuZ3RoIjo0NiwiaGFzaGVzIjp7InNoYTI1NiI6IjEzYTc2OTJmNjI1ZjUyMjU2NDhjYzZiNjIzOGM5ZmJiZDIyMGJjYmIxNTkzN2E3NDkwMTFjZGY2NTIwNWUyMTMifSwiY3VzdG9tIjp7InYiOjF9fX19LCJzaWduYXR1cmVzIjpbeyJrZXlpZCI6ImVkNzY3MmM5YTI0YWJkYTc4ODcyZWUzMmVlNzFjN2NiMWQ1MjM1ZThkYjRlY2JmMWNhMjhiOWM1MGViNzVkOWUiLCJzaWciOiJlMTZjM2M3MDM1ZmZiYmZjY2ZhNGUwYTJlYTc3YzNiYzc4ZmI3MmU3Mzc0YmQ2MWYwOTFiYWMyNDFjYzEzY2MyNmRjNGU0YTJlMWMwYTM4YjJmZjgwNmM4Y2U4ZTJjNmM4NDc5NTQ0NGRmYTUxMTBkOTc4M2E2ZTMxMzViYWMwMSJ9XX0=","target_files":[{"path":"datadog/2/ASM_DD/thisshouldalsobeignored/config","raw":"ImFXZHViM0psYldWaFoyRnBiZz09Ig=="}],"client_configs":["datadog/2/ASM_DD/asmdd1/config","datadog/2/FEATURES/features1/config","datadog/2/FEATURES/features3/config","datadog/2/ASM_DD/asmdd4/config"]}'
                ]

                if self.config_request_count + 1 > len(CONFIG_CONTENTS):
                    content = b'{}'  # default content when there isn't an RC update
                else:
                    content = CONFIG_CONTENTS[self.config_request_count]

                flow.response.status_code = 200
                flow.response.content = content

                self.config_request_count += 1


addons = [Forwarder()]
