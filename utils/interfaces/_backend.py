# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

""" This files will validate data flow between agent and backend """

import json
import os
import time

import requests

from utils.interfaces._core import InterfaceValidator, get_rid_from_span, get_rid_from_request
from utils.tools import logger


BACKEND_LOCAL_PORT = 11111


class _BackendInterfaceValidator(InterfaceValidator):
    """Validate backend data processors"""

    def __init__(self):
        super().__init__("backend")

        # Mapping from request ID to the root span trace IDs submitted from tracers to agent.
        self.rid_to_library_trace_ids = {}

    # Called by the test setup to make sure the interface is ready.
    def wait(self, timeout):
        super().wait(timeout, stop_accepting_data=False)

        from utils.interfaces import library

        # Map each request ID to the spans created and submitted during that request call.
        for _, span in library.get_root_spans():
            rid = get_rid_from_span(span)

            if not self.rid_to_library_trace_ids.get(rid):
                self.rid_to_library_trace_ids[rid] = [span["trace_id"]]
            else:
                self.rid_to_library_trace_ids[rid].append(span["trace_id"])

    #################################
    ######### API for tests #########
    #################################

    def assert_library_traces_exist(self, request, min_traces_len=1):
        """Attempts to fetch from the backend, ALL the traces that the library tracers sent to the agent
        during the execution of the given request.

        The assosiation of the traces with a request is done through propagating the request ID (inside user agent)
        on all the submitted traces. This is done automatically, unless you create root spans manually, which in
        that case you need to manually propagate the user agent to the new spans.

        It will assert that at least `min_traces_len` were received from the backend before
        returning the list of traces.
        """

        rid = get_rid_from_request(request)
        tracesData = list(self._wait_for_request_traces(rid))
        traces = [self._extract_trace_from_backend_response(data["response"]) for data in tracesData]
        assert (
            len(traces) >= min_traces_len
        ), f"We only found {len(traces)} traces in the library (tracers), but we expected {min_traces_len}!"
        return traces

    def assert_otlp_trace_exist(self, request: requests.Request, dd_trace_id: str) -> dict:
        """Attempts to fetch from the backend, ALL the traces that the OpenTelemetry SDKs sent to Datadog
        during the execution of the given request.

        The assosiation of the traces with a request is done through propagating the request ID (inside user agent)
        on all the submitted traces. This is done automatically, unless you create root spans manually, which in
        that case you need to manually propagate the user agent to the new spans.
        """

        rid = get_rid_from_request(request)
        data = self._wait_for_trace(rid=rid, trace_id=dd_trace_id, retries=10, sleep_interval_multiplier=2.0)
        return json.loads(data["response"]["content"])["trace"]

    def assert_single_spans_exist(self, request, min_spans_len=1, limit=100):
        """Attempts to fetch single span events using the given `query_filter` as part of the search query.
        The query should be what you would use in the `/apm/traces` page in the UI.

        When a valid request is provided we will restrict the single span search to span events
        that include the request ID in their tags.

        It will assert that at least `min_spans_len` were received from the backend before
        returning the list of span events.
        """

        rid = get_rid_from_request(request)
        query_filter = f"service:weblog @single_span:true @http.useragent:*{rid}"
        return self.assert_request_spans_exist(request, query_filter, min_spans_len, limit)

    def assert_request_spans_exist(self, request, query_filter, min_spans_len=1, limit=100):
        """Attempts to fetch span events from the Event Platform using the given `query_filter` as part of the search query.
        The query should be what you would use in the `/apm/traces` page in the UI.
        When a valid request is provided we will restrict the span search to span events
        that include the request ID in their tags.

        It will assert that at least `min_spans_len` were received from the backend before
        returning the list of span events.
        """

        rid = get_rid_from_request(request)
        if rid:
            query_filter = f"{query_filter} @http.useragent:*{rid}"

        return self.assert_spans_exist(query_filter, min_spans_len, limit)

    def assert_spans_exist(self, query_filter, min_spans_len=1, limit=100):
        """Attempts to fetch span events from the Event Platform using the given `query_filter` as part of the search query.
        The query should be what you would use in the `/apm/traces` page in the UI.

        It will assert that at least `min_spans_len` were received from the backend before
        returning the list of span events.
        """

        logger.debug(f"We will attempt to fetch span events with query filter: {query_filter}")
        data = self._wait_for_event_platform_spans(query_filter, limit)

        result = data["response"]["contentJson"]["result"]
        assert result["count"] >= min_spans_len, f"Did not have the expected number of spans ({min_spans_len}): {data}"

        return [item["event"] for item in result["events"]]

    ############################################
    ######### Internal implementation ##########
    ############################################

    def _get_trace_ids(self, rid):
        if rid not in self.rid_to_library_trace_ids:
            raise Exception("There is no trace id related to this request ")

        return self.rid_to_library_trace_ids[rid]

    def _get_backend_trace_data(self, rid, trace_id):
        # We use `localhost` as host since we run a proxy that forwards the requests to the right
        # backend DD_SITE domain, and logs the request/response as well.
        # More details in `utils.proxy.core.get_dd_site_api_host()`.
        host = f"http://localhost:{BACKEND_LOCAL_PORT}"
        path = f"/api/v1/trace/{trace_id}"

        headers = {
            "DD-API-KEY": os.environ["DD_API_KEY"],
            "DD-APPLICATION-KEY": os.environ.get("DD_APP_KEY", os.environ["DD_APPLICATION_KEY"]),
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

    def _wait_for_request_traces(self, rid, retries=5, sleep_interval_multiplier=2.0):
        if retries < 1:
            retries = 1

        trace_ids = self._get_trace_ids(rid)
        logger.info(
            f"Waiting for {len(trace_ids)} traces to become available from request {rid} with {retries} retries..."
        )
        for trace_id in trace_ids:
            logger.info(
                f"Waiting for trace {trace_id} to become available from request {rid} with {retries} retries..."
            )
            yield self._wait_for_trace(rid, trace_id, retries, sleep_interval_multiplier)

    def _extract_trace_from_backend_response(self, response):
        content_parsed = json.loads(response["content"])
        trace = content_parsed.get("trace")
        if not trace:
            raise Exception(f"The response does not contain valid trace content: {response}")
        return trace

    def _wait_for_event_platform_spans(self, query_filter, limit, retries=5, sleep_interval_multiplier=2.0):
        if retries < 1:
            retries = 1

        logger.info(
            f"Waiting until spans (non-empty response) become available with query '{query_filter}' with {retries} retries..."
        )
        sleep_interval_s = 1
        current_retry = 1
        while current_retry <= retries:
            logger.info(f"Retry {current_retry}")
            current_retry += 1

            data = self._get_event_platform_spans(query_filter, limit)

            # We should retry fetching from the backend as long as the response has empty data.
            status_code = data["response"]["status_code"]
            if status_code != 200:
                raise Exception(f"Fetching spans from Event Platform failed: {data['path']}. Status is {status_code}.")

            parsed = data["response"]["contentJson"]
            if parsed["result"]["count"] > 0:
                return data

            time.sleep(sleep_interval_s)
            sleep_interval_s *= sleep_interval_multiplier  # increase the sleep time with each retry

        # We always try once so `data` should have not be None.
        return data

    def _get_event_platform_spans(self, query_filter, limit):
        # Example of this query can be seen in the `events-ui` internal website (see Jira ATI-2419).
        # We use `localhost` as host since we run a proxy that forwards the requests to the right
        # backend DD_SITE domain, and logs the request/response as well.
        # More details in `utils.proxy.core.get_dd_site_api_host()`.
        host = f"http://localhost:{BACKEND_LOCAL_PORT}"
        path = "/api/unstable/event-platform/analytics/list?type=trace"

        headers = {
            "DD-API-KEY": os.environ["DD_API_KEY"],
            "DD-APPLICATION-KEY": os.environ.get("DD_APP_KEY", os.environ["DD_APPLICATION_KEY"]),
        }

        request_data = {
            "list": {
                "search": {"query": f"env:system-tests {query_filter}",},
                "indexes": ["trace-search"],
                "time": {
                    # 30 min of window should be plenty
                    "from": "now-1800s",
                    "to": "now",
                },
                "limit": limit,
                "columns": [],
                "computeCount": True,
                "includeEventContents": True,
            }
        }
        r = requests.post(f"{host}{path}", json=request_data, headers=headers, timeout=10)

        contentJson = None
        try:
            contentJson = r.json()
        except:
            pass

        data = {
            "host": host,
            "path": path,
            "response": {
                "status_code": r.status_code,
                "content": r.text,
                "contentJson": contentJson,
                "headers": dict(r.headers),
            },
        }

        return data
