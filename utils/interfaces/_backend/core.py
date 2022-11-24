# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""
This files will validate data flow between agent and backend
"""

import os
import threading
import requests

from utils.interfaces._core import BaseValidation, InterfaceValidator
from utils.tools import logger


class _BackendInterfaceValidator(InterfaceValidator):
    """Validate backend data processors"""

    def __init__(self):
        super().__init__("backend")
        self.ready = threading.Event()
        self.ready.set()

    def get_expected_timeout(self, context):
        return 5

    def collect_data(self):
        from utils.interfaces import library
        from utils.interfaces._library._utils import _get_rid_from_span

        logger.info(f"Get data for {self.rids}")
        for data in library._data_list:
            if data["path"] not in ("/v0.4/traces", "/v0.5/traces"):
                continue

            for trace in data["request"]["content"]:
                for span in trace:
                    if span.get("parent_id") in (0, None):
                        rid = _get_rid_from_span(span)
                        trace_id = span.get("trace_id")
                        if rid and rid in self.rids:
                            logger.info(f"Found rid/trace_id: {rid} -> {trace_id}, collect data from backend")
                            path = f"/api/v1/trace/{trace_id}"
                            host = "https://dd.datad0g.com"

                            headers = {
                                "DD-API-KEY": os.environ["DD_API_KEY"],
                                "DD-APPLICATION-KEY": os.environ["DD_APPLICATION_KEY"],
                            }
                            r = requests.get(f"{host}{path}", headers=headers)

                            self.append_data(
                                {
                                    "host": host,
                                    "path": path,
                                    "rid": rid,
                                    "response": {
                                        "status_code": r.status_code,
                                        "content": r.text,
                                        "headers": dict(r.headers),
                                    },
                                }
                            )
                        elif rid:
                            logger.info(f"Found rid/trace_id: {rid} -> {trace_id}, but I don't need it")

    def assert_waf_attack(self, request):
        self.append_validation(_AssertWafAttack(request=request))


class _AssertWafAttack(BaseValidation):
    def __init__(self, request):
        super().__init__(request=request)

    def check(self, data):
        if data["rid"] == self.rid:

            status_code = data["response"]["status_code"]
            if status_code != 200:
                self.set_failure(f"Backend did not provide trace: {data['path']}. Status is {status_code}")
                return

            trace = data["response"]["content"].get("trace", {})
            for span in trace.get("spans", {}).values():
                if not span["parent_id"] in (None, 0, "0"):  # only root span
                    continue

                meta = span.get("meta", {})

                if "_dd.appsec.source" not in meta:
                    self.set_failure(f"'_dd.appsec.source' should be in span's meta tags")

                elif meta["_dd.appsec.source"] != "backendwaf":
                    self.set_failure(
                        f"'_dd.appsec.source' values should be 'backendwaf', not {meta['_dd.appsec.source']} in {data['log_filename']}"
                    )

                elif "appsec" not in meta:
                    self.set_failure(f"'appsec' should be in span's meta tags in {data['log_filename']}")

                else:
                    self.set_status(True)
                    return
