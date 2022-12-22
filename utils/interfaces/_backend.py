# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

""" This files will validate data flow between agent and backend """

import os
import threading
import requests

from utils.interfaces._core import InterfaceValidator, get_rid_from_span, get_rid_from_request


class _BackendInterfaceValidator(InterfaceValidator):
    """Validate backend data processors"""

    def __init__(self):
        super().__init__("backend")
        self.ready = threading.Event()
        self.ready.set()
        self.timeout = 5

        self.rid_to_trace_id = {}

    def wait(self):
        super().wait()
        from utils.interfaces import library

        for _, _, span in library.get_spans():
            if span.get("parent_id") in (0, None):
                rid = get_rid_from_span(span)
                self.rid_to_trace_id[rid] = span.get("trace_id")

    def _get_backend_data(self, request):
        rid = get_rid_from_request(request)

        if rid not in self.rid_to_trace_id:
            raise Exception("There is no trace id related to this request ")

        trace_id = self.rid_to_trace_id[rid]

        path = f"/api/v1/trace/{trace_id}"
        host = "https://dd.datad0g.com"

        headers = {
            "DD-API-KEY": os.environ["DD_API_KEY"],
            "DD-APPLICATION-KEY": os.environ["DD_APPLICATION_KEY"],
        }
        r = requests.get(f"{host}{path}", headers=headers, timeout=10)

        return {
            "host": host,
            "path": path,
            "rid": rid,
            "response": {
                "status_code": r.status_code,
                "content": r.text,
                "headers": dict(r.headers),
            },
        }

    def assert_waf_attack(self, request):
        data = self._get_backend_data(request)

        status_code = data["response"]["status_code"]
        if status_code != 200:
            raise Exception(f"Backend did not provide trace: {data['path']}. Status is {status_code}")

        trace = data["response"]["content"].get("trace", {})
        for span in trace.get("spans", {}).values():
            if not span["parent_id"] in (None, 0, "0"):  # only root span
                continue

            meta = span.get("meta", {})

            assert "_dd.appsec.source" in meta, "'_dd.appsec.source' should be in span's meta tags"
            assert "appsec" in meta, f"'appsec' should be in span's meta tags in {data['log_filename']}"

            assert meta["_dd.appsec.source"] == "backendwaf", (
                f"'_dd.appsec.source' values should be 'backendwaf', "
                f"not {meta['_dd.appsec.source']} in {data['log_filename']}"
            )
