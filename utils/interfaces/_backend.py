# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

""" This files will validate data flow between agent and backend """

import json
import os
import threading
import requests
import time

from utils.interfaces._core import InterfaceValidator, get_rid_from_span, get_rid_from_request
from utils.tools import logger


class _BackendInterfaceValidator(InterfaceValidator):
    """Validate backend data processors"""

    def __init__(self):
        super().__init__("backend")
        self.ready = threading.Event()
        self.ready.set()
        self.timeout = 5

        self.rid_to_trace_id = {}

    # Called by the test setup to make sure the interface is ready.
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
            "response": {"status_code": r.status_code, "content": r.text, "headers": dict(r.headers),},
        }

    def _wait_for_request_trace(self, request, retries=5, sleep_interval_multiplier=2.0):
        if retries < 1:
            retries = 1

        rid = get_rid_from_request(request)
        logger.info(f"Waiting for a trace to become available from request {rid} with {retries} retries...")

        sleep_interval_s = 1
        current_retry = 1
        while current_retry <= retries:
            logger.info(f"Retry {current_retry}")
            current_retry += 1

            data = self._get_backend_data(request)

            # We should retry fetching from the backend as long as the response is 404.
            status_code = data["response"]["status_code"]
            if status_code != 404 and status_code != 200:
                raise Exception(f"Backend did not provide trace: {data['path']}. Status is {status_code}.")
            if status_code != 404:
                return data

            time.sleep(sleep_interval_s)
            sleep_interval_s *= sleep_interval_multiplier # increase the sleep time with each retry

        raise Exception(f"Backend did not provide trace after {retries} retries: {data['path']}. Status is {status_code}.")

    def _extract_trace_from_backend_response(self, response):
        content_parsed = json.loads(response["content"])
        trace = content_parsed.get("trace")
        if not trace: 
            raise Exception(f"The response does not contain valid trace content: {response}")
        return trace

    def assert_trace_exists(self, request):
        data = self._wait_for_request_trace(request)
        trace = self._extract_trace_from_backend_response(data["response"])
        return trace

    # The following is not used!
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
