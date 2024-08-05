# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""
This files will validate data flow between agent and backend
"""

import threading
import copy

from utils.tools import logger, get_rid_from_span, get_rid_from_request
from utils.interfaces._core import ProxyBasedInterfaceValidator
from utils.interfaces._misc_validators import HeadersPresenceValidator, HeadersMatchValidator


class AgentInterfaceValidator(ProxyBasedInterfaceValidator):
    """Validate agent/backend interface"""

    def __init__(self):
        super().__init__("agent")
        self.ready = threading.Event()

    def ingest_file(self, src_path):
        self.ready.set()
        return super().ingest_file(src_path)

    def get_appsec_data(self, request):

        rid = get_rid_from_request(request)

        for data in self.get_data(path_filters="/api/v0.2/traces"):
            if "tracerPayloads" not in data["request"]["content"]:
                continue

            content = data["request"]["content"]["tracerPayloads"]

            for payload in content:
                for chunk in payload["chunks"]:
                    for span in chunk["spans"]:
                        appsec_data = span.get("meta", {}).get("_dd.appsec.json", None) or span.get(
                            "meta_struct", {}
                        ).get("appsec", None)
                        if appsec_data is None:
                            continue

                        if rid is None:
                            yield data, payload, chunk, span, appsec_data
                        elif get_rid_from_span(span) == rid:
                            logger.debug(f'Found span with rid={rid} in {data["log_filename"]}')
                            yield data, payload, chunk, span, appsec_data

    def assert_use_domain(self, expected_domain):
        # TODO: Move this in test class

        for data in self.get_data():
            domain = data["host"][-len(expected_domain) :]

            if domain != expected_domain:
                raise ValueError(f"Message #{data['log_filename']} uses host {domain} instead of {expected_domain}")

    def get_profiling_data(self):
        yield from self.get_data(path_filters="/api/v2/profile")

    def validate_appsec(self, request, validator):
        for data, payload, chunk, span, appsec_data in self.get_appsec_data(request=request):
            if validator(data, payload, chunk, span, appsec_data):
                return

        raise ValueError("No data validate this test")

    def get_telemetry_data(self, flatten_message_batches=True):
        all_data = self.get_data(path_filters="/api/v2/apmtelemetry")
        if flatten_message_batches:
            yield from all_data
        else:
            for data in all_data:
                if data["request"]["content"].get("request_type") == "message-batch":
                    for batch_payload in data["request"]["content"]["payload"]:
                        # create a fresh copy of the request for each payload in the
                        # message batch, as though they were all sent independently
                        copied = copy.deepcopy(data)
                        copied["request"]["content"]["request_type"] = batch_payload.get("request_type")
                        copied["request"]["content"]["payload"] = batch_payload.get("payload")
                        yield copied
                else:
                    yield data

    def assert_headers_presence(self, path_filter, request_headers=(), response_headers=(), check_condition=None):
        validator = HeadersPresenceValidator(request_headers, response_headers, check_condition)
        self.validate(validator, path_filters=path_filter, success_by_default=True)

    def assert_headers_match(self, path_filter, request_headers=(), response_headers=(), check_condition=None):
        validator = HeadersMatchValidator(request_headers, response_headers, check_condition)
        self.validate(validator, path_filters=path_filter, success_by_default=True)

    def validate_telemetry(self, validator=None, success_by_default=False):
        def validator_skip_onboarding_event(data):
            if data["request"]["content"].get("request_type") == "apm-onboarding-event":
                return None
            return validator(data)

        self.validate(
            validator=validator_skip_onboarding_event,
            success_by_default=success_by_default,
            path_filters="/api/v2/apmtelemetry",
        )

    def add_traces_validation(self, validator, success_by_default=False):
        self.validate(
            validator=validator, success_by_default=success_by_default, path_filters=r"/api/v0\.[1-9]+/traces"
        )

    def get_spans(self, request=None):
        """Attempts to fetch the spans the agent will submit to the backend.

        When a valid request is given, then we filter the spans to the ones sampled
        during that request's execution, and only return those.
        """

        rid = get_rid_from_request(request)
        if rid:
            logger.debug(f"Will try to find agent spans related to request {rid}")

        for data in self.get_data(path_filters="/api/v0.2/traces"):
            if "tracerPayloads" not in data["request"]["content"]:
                raise ValueError("Trace property is missing in agent payload")

            content = data["request"]["content"]["tracerPayloads"]

            for payload in content:
                for chunk in payload["chunks"]:
                    for span in chunk["spans"]:
                        if rid is None:
                            yield data, span
                        elif get_rid_from_span(span) == rid:
                            yield data, span

    def get_spans_list(self, request):
        return [span for _, span in self.get_spans(request)]

    def get_dsm_data(self):
        return self.get_data(path_filters="/api/v0.1/pipeline_stats")

    def get_stats(self, resource=""):
        """Attempts to fetch the stats the agent will submit to the backend.

        When a valid request is given, then we filter the stats to the ones sampled
        during that request's execution, and only return those.
        """

        for data in self.get_data(path_filters="/api/v0.2/stats"):
            client_stats_payloads = data["request"]["content"]["Stats"]

            for client_stats_payload in client_stats_payloads:
                for client_stats_buckets in client_stats_payload["Stats"]:
                    for client_grouped_stat in client_stats_buckets["Stats"]:
                        if resource == "":
                            yield client_grouped_stat
                        elif client_grouped_stat["Resource"] == resource:
                            yield client_grouped_stat
