# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

""" This files will validate data flow between agent and backend """

import json
import os
import time

import requests

from utils.interfaces._core import ProxyBasedInterfaceValidator
from utils.tools import logger, get_rid_from_span, get_rid_from_request


class _BackendInterfaceValidator(ProxyBasedInterfaceValidator):
    """Validate backend data processors"""

    def __init__(self, library_interface):
        super().__init__("backend")

        # Mapping from request ID to the root span trace IDs submitted from tracers to agent.
        self.rid_to_library_trace_ids = {}
        self.dd_site_url = self._get_dd_site_api_host()
        self.message_count = 0

        self.library_interface = library_interface

    @staticmethod
    def _get_dd_site_api_host():
        # https://docs.datadoghq.com/getting_started/site/#access-the-datadog-site
        # DD_SITE => API HOST
        # datad0g.com       => dd.datad0g.com
        # datadoghq.com     => app.datadoghq.com
        # datadoghq.eu      => app.datadoghq.eu
        # ddog-gov.com      => app.ddog-gov.com
        # XYZ.datadoghq.com => XYZ.datadoghq.com

        dd_site = os.environ.get("DD_SITE", "datad0g.com")
        dd_site_to_app = {
            "datad0g.com": "https://dd.datad0g.com",
            "datadoghq.com": "https://app.datadoghq.com",
            "datadoghq.eu": "https://app.datadoghq.eu",
            "ddog-gov.com": "https://app.ddog-gov.com",
            "us3.datadoghq.com": "https://us3.datadoghq.com",
            "us5.datadoghq.com": "https://us5.datadoghq.com",
        }
        dd_app_url = dd_site_to_app.get(dd_site)
        assert dd_app_url is not None, f"We could not resolve a proper Datadog API URL given DD_SITE[{dd_site}]!"

        logger.debug(f"Using Datadog API URL[{dd_app_url}] as resolved from DD_SITE[{dd_site}].")
        return dd_app_url

    def stop(self):
        super().stop()
        self._init_rid_to_library_trace_ids()

    def load_data_from_logs(self):
        super().load_data_from_logs()
        self._init_rid_to_library_trace_ids()

    def _init_rid_to_library_trace_ids(self):

        # Map each request ID to the spans created and submitted during that request call.
        for _, span in self.library_interface.get_root_spans():
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

    def assert_otlp_trace_exist(
        self, request: requests.Request, dd_trace_id: str, dd_api_key: str = None, dd_app_key: str = None
    ) -> dict:
        """Attempts to fetch from the backend, ALL the traces that the OpenTelemetry SDKs sent to Datadog
        during the execution of the given request.

        The assosiation of the traces with a request is done through propagating the request ID (inside user agent)
        on all the submitted traces. This is done automatically, unless you create root spans manually, which in
        that case you need to manually propagate the user agent to the new spans.
        """

        rid = get_rid_from_request(request)
        data = self._wait_for_trace(
            rid=rid,
            trace_id=dd_trace_id,
            retries=5,
            sleep_interval_multiplier=2.0,
            dd_api_key=dd_api_key,
            dd_app_key=dd_app_key,
        )
        return data["response"]["content"]["trace"]

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
        """Attempts to fetch span events from the Event Platform using the given `query_filter`
        as part of the search query. The query should be what you would use in the `/apm/traces`
        page in the UI. When a valid request is provided we will restrict the span search to span
        events that include the request ID in their tags.

        It will assert that at least `min_spans_len` were received from the backend before
        returning the list of span events.
        """

        rid = get_rid_from_request(request)
        if rid:
            query_filter = f"{query_filter} @http.useragent:*{rid}"

        return self.assert_spans_exist(query_filter, min_spans_len, limit)

    def assert_spans_exist(self, query_filter, min_spans_len=1, limit=100):
        """Attempts to fetch span events from the Event Platform using the given `query_filter`
        as part of the search query. The query should be what you would use in the `/apm/traces`
        page in the UI.

        It will assert that at least `min_spans_len` were received from the backend before
        returning the list of span events.
        """

        logger.debug(f"We will attempt to fetch span events with query filter: {query_filter}")
        data = self._wait_for_event_platform_spans(query_filter, limit)

        result = data["response"]["content"]["result"]
        assert result["count"] >= min_spans_len, f"Did not have the expected number of spans ({min_spans_len}): {data}"

        return [item["event"] for item in result["events"]]

    ############################################
    ######### Internal implementation ##########
    ############################################

    def _get_trace_ids(self, rid):
        if rid not in self.rid_to_library_trace_ids:
            raise ValueError("There is no trace id related to this request ")

        return self.rid_to_library_trace_ids[rid]

    def _request(self, method, path, host=None, json_payload=None, dd_api_key=None, dd_app_key=None):
        while True:
            data = self._request_one(
                method=method,
                path=path,
                host=host,
                json_payload=json_payload,
                dd_api_key=dd_api_key,
                dd_app_key=dd_app_key,
            )
            status_code = data["response"]["status_code"]
            if status_code == 429:
                # https://docs.datadoghq.com/api/latest/rate-limits/
                logger.debug(f"Got rate limit error: {data['response']}")
                sleep_time_s = int(data["response"]["headers"]["x-ratelimit-reset"])
                logger.warning(f"Rate limit hit, sleeping {sleep_time_s}")
                time.sleep(sleep_time_s)
                continue
            return data

    def _request_one(self, method, path, host=None, json_payload=None, dd_api_key=None, dd_app_key=None):
        if dd_api_key is None:
            dd_api_key = os.environ["DD_API_KEY"]
        if dd_app_key is None:
            dd_app_key = os.environ.get("DD_APP_KEY", os.environ["DD_APPLICATION_KEY"])
        headers = {
            "DD-API-KEY": dd_api_key,
            "DD-APPLICATION-KEY": dd_app_key,
        }

        if host is None:
            host = self.dd_site_url
        r = requests.request(method, url=f"{host}{path}", headers=headers, json=json_payload, timeout=10)

        if r.status_code == 403:
            raise ValueError(
                "Request to the backend returned error 403: check DD_API_KEY and DD_APP_KEY environment variables"
            )

        if "?" in path:
            path, query = path.split("?", 1)
        else:
            query = ""
        data = {
            "host": host,
            "path": path,
            "query": query,
            "request": {"content": json_payload},
            "response": {"status_code": r.status_code, "content": r.content, "headers": dict(r.headers),},
            "log_filename": f"{self._log_folder}/{self.message_count:03d}_{path.replace('/', '_')}.json",
        }
        self.message_count += 1

        try:
            data["response"]["content"] = r.json()
        except:
            data["response"]["content"] = r.text

        with open(data["log_filename"], mode="w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return data

    def _get_backend_trace_data(self, rid, trace_id, dd_api_key=None, dd_app_key=None):
        path = f"/api/v1/trace/{trace_id}"
        result = self._request("GET", path=path, dd_api_key=dd_api_key, dd_app_key=dd_app_key)
        result["rid"] = rid

        return result

    def _wait_for_trace(self, rid, trace_id, retries, sleep_interval_multiplier, dd_api_key=None, dd_app_key=None):
        sleep_interval_s = 1
        current_retry = 1
        while current_retry <= retries:
            logger.info(f"Retry {current_retry}")
            current_retry += 1

            data = self._get_backend_trace_data(rid, trace_id, dd_api_key, dd_app_key)

            # We should retry fetching from the backend as long as the response is 404.
            status_code = data["response"]["status_code"]
            if status_code not in (404, 200):
                raise ValueError(f"Backend did not provide trace: {data['path']}. Status is {status_code}.")
            if status_code != 404:
                return data

            logger.debug(f"Sleeping {sleep_interval_s} seconds")
            time.sleep(sleep_interval_s)
            sleep_interval_s *= sleep_interval_multiplier  # increase the sleep time with each retry

        raise ValueError(
            f"Backend did not provide trace after {retries} retries: {data['path']}. Status is {status_code}."
        )

    def _wait_for_request_traces(self, rid, retries=5, sleep_interval_multiplier=2.0):

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
        trace = response["content"].get("trace")
        if not trace:
            raise ValueError(f"The response does not contain valid trace content:\n{json.dumps(response, indent=2)}")

        return trace

    def _wait_for_event_platform_spans(self, query_filter, limit, retries=5, sleep_interval_multiplier=2.0):

        logger.info(
            f"Waiting until spans (non-empty response) become available with "
            f"query '{query_filter}' with {retries} retries..."
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
                raise ValueError(f"Fetching spans from Event Platform failed: {data['path']}. Status is {status_code}.")

            parsed = data["response"]["content"]
            if parsed["result"]["count"] > 0:
                return data

            time.sleep(sleep_interval_s)
            sleep_interval_s *= sleep_interval_multiplier  # increase the sleep time with each retry

        # We always try once so `data` should have not be None.
        return data

    def _get_event_platform_spans(self, query_filter, limit):
        # Example of this query can be seen in the `events-ui` internal website (see Jira ATI-2419).
        path = "/api/unstable/event-platform/analytics/list?type=trace"

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

        return self._request("POST", path, json_payload=request_data)

    # Queries the backend metric timeseries API and returns the matched series.
    def query_timeseries(
        self,
        rid: str,
        start: int,
        end: int,
        metric: str,
        dd_api_key=None,
        dd_app_key=None,
        retries=10,
        sleep_interval_multiplier=2.0,
        initial_delay_s=10.0,
    ):
        query = metric + "{rid:" + rid + "}"
        path = f"/api/v1/query?from={start}&to={end}&query={query}"
        sleep_interval_s = 1
        current_retry = 1
        # It takes very long for metric timeseries to be query-able.
        time.sleep(initial_delay_s)
        while current_retry <= retries:
            logger.info(f"Retry {current_retry}")
            current_retry += 1
            data = self._request(
                "GET", host=self._get_logs_metrics_api_host(), path=path, dd_api_key=dd_api_key, dd_app_key=dd_app_key
            )
            # We should retry fetching from the backend as long as the response is 404.
            status_code = data["response"]["status_code"]
            if status_code not in (404, 200):
                raise ValueError(f"Backend did not provide metric: {data['path']}. Status is {status_code}.")
            if status_code != 404:
                resp_content = data["response"]["content"]
                # There may be delay in metric query, retry when series are not present
                if len(resp_content["series"]) > 0:
                    return resp_content

            time.sleep(sleep_interval_s)
            sleep_interval_s *= sleep_interval_multiplier  # increase the sleep time with each retry

        raise ValueError(
            f"Backend did not provide metric series after {retries} retries: {data['path']}. Status is {status_code}."
        )

    # Queries the backend log search API and returns the log matching the given query.
    def get_logs(
        self, query: str, rid: str, dd_api_key=None, dd_app_key=None, retries=8, sleep_interval_multiplier=2.0
    ):
        path = f"/api/v2/logs/events?query={query}"
        sleep_interval_s = 1
        current_retry = 1
        while current_retry <= retries:
            logger.info(f"Getting logs from {path}, retry {current_retry}")
            current_retry += 1
            data = self._request(
                "GET", host=self._get_logs_metrics_api_host(), path=path, dd_api_key=dd_api_key, dd_app_key=dd_app_key
            )
            # We should retry fetching from the backend as long as the response is 404.
            status_code = data["response"]["status_code"]
            if status_code not in (404, 200):
                logger.error(f"Backend response: {data['response']}")
                raise ValueError(f"Backend did not provide logs: {data['path']}. Status is {status_code}.")
            if status_code != 404:
                logs = data["response"]["content"]["data"]
                # Log search can sometimes return wrong results. Retry if expected log is not present.
                for log in logs:
                    if rid in log["attributes"]["message"]:
                        return log

            time.sleep(sleep_interval_s)
            sleep_interval_s *= sleep_interval_multiplier  # increase the sleep time with each retry

        raise ValueError(
            f"Backend did not provide logs after {retries} retries: {data['path']}. Status is {status_code}."
        )

    @staticmethod
    def _get_logs_metrics_api_host() -> str:
        dd_site = os.environ.get("DD_SITE", "datad0g.com")
        return f"https://api.{dd_site}"
