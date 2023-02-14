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

        # Mapping from request ID to the root span trace IDs submitted from tracers to agent.
        self.rid_to_library_trace_ids = {}

    # Called by the test setup to make sure the interface is ready.
    def wait(self):
        super().wait()
        from utils.interfaces import library

        # Map each request ID to the spans created and submitted during that request call.
        for _, span in library.get_root_spans():
            rid = get_rid_from_span(span)

            if not self.rid_to_library_trace_ids.get(rid):
                self.rid_to_library_trace_ids[rid] = [span["trace_id"]]
            else:
                self.rid_to_library_trace_ids[rid].append(span["trace_id"])

    def _get_trace_ids(self, request):
        rid = get_rid_from_request(request)

        if rid not in self.rid_to_library_trace_ids:
            raise Exception("There is no trace id related to this request ")

        return self.rid_to_library_trace_ids[rid]

    def _get_backend_trace_data(self, rid, trace_id):
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

    def _wait_for_trace(self, rid, trace_id, retries, sleep_interval_multiplier):
        sleep_interval_s = 1
        current_retry = 1
        while current_retry <= retries:
            logger.info(f"Retry {current_retry}")
            current_retry += 1

            data = self._get_backend_trace_data(rid, trace_id)

            # We should retry fetching from the backend as long as the response is 404.
            status_code = data["response"]["status_code"]
            if status_code != 404 and status_code != 200:
                raise Exception(f"Backend did not provide trace: {data['path']}. Status is {status_code}.")
            if status_code != 404:
                return data

            time.sleep(sleep_interval_s)
            sleep_interval_s *= sleep_interval_multiplier  # increase the sleep time with each retry

        raise Exception(
            f"Backend did not provide trace after {retries} retries: {data['path']}. Status is {status_code}."
        )

    def _wait_for_request_traces(self, request, retries=5, sleep_interval_multiplier=2.0):
        rid = get_rid_from_request(request)
        if retries < 1:
            retries = 1

        trace_ids = self._get_trace_ids(request)
        logger.info(f"Waiting for {len(trace_ids)} traces to become available from request {rid} with {retries} retries...")
        for trace_id in trace_ids:
            logger.info(f"Waiting for trace {trace_id} to become available from request {rid} with {retries} retries...")
            yield self._wait_for_trace(rid, trace_id, retries, sleep_interval_multiplier)

    def _extract_trace_from_backend_response(self, response):
        content_parsed = json.loads(response["content"])
        trace = content_parsed.get("trace")
        if not trace:
            raise Exception(f"The response does not contain valid trace content: {response}")
        return trace

    def assert_library_traces_exist(self, request, min_traces_len=1):
        tracesData = self._wait_for_request_traces(request)
        assert len(tracesData) > min_traces_len, f"We only found {len(tracesData)} traces in the library (tracers), but we expected {min_traces_len}!"
        return [self._extract_trace_from_backend_response(data["response"]) for data in tracesData]

