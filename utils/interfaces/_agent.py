# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""
This files will validate data flow between agent and backend
"""

import json
import threading

from utils.tools import logger
from utils.interfaces._core import InterfaceValidator, get_rid_from_request, get_rid_from_span
from utils.interfaces._schemas_validators import SchemaValidator
from utils.interfaces._profiling import _ProfilingFieldValidator
from utils.interfaces._misc_validators import HeadersPresenceValidator, HeadersMatchValidator


class AgentInterfaceValidator(InterfaceValidator):
    """Validate agent/backend interface"""

    def __init__(self):
        super().__init__("agent")
        self.ready = threading.Event()
        self.timeout = 5

    def append_data(self, data):
        data = super().append_data(data)

        self.ready.set()

        return data

    def get_appsec_data(self, request):

        rid = get_rid_from_request(request)

        for data in self.get_data(path_filters="/api/v0.2/traces"):
            if "tracerPayloads" not in data["request"]["content"]:
                continue

            content = data["request"]["content"]["tracerPayloads"]

            for payload in content:
                for chunk in payload["chunks"]:
                    for span in chunk["spans"]:

                        if "meta" not in span or "_dd.appsec.json" not in span["meta"]:
                            continue

                        appsec_data = json.loads(span["meta"]["_dd.appsec.json"])

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
                raise Exception(f"Message #{data['log_filename']} uses host {domain} instead of {expected_domain}")

    def assert_schemas(self, allowed_errors=None):
        validator = SchemaValidator("agent", allowed_errors)
        self.validate(validator, success_by_default=True)

    def add_profiling_validation(self, validator, success_by_default=False):
        self.validate(validator, path_filters="/api/v2/profile", success_by_default=success_by_default)

    def profiling_assert_field(self, field_name, content_pattern=None):
        self.timeout = 160
        self.add_profiling_validation(_ProfilingFieldValidator(field_name, content_pattern), success_by_default=True)

    def validate_appsec(self, request, validator):
        for data, payload, chunk, span, appsec_data in self.get_appsec_data(request=request):
            if validator(data, payload, chunk, span, appsec_data):
                return

        raise Exception("No data validate this test")

    def get_telemetry_data(self):
        yield from self.get_data(path_filters="/api/v2/apmtelemetry")

    def assert_headers_presence(self, path_filter, request_headers=(), response_headers=(), check_condition=None):
        validator = HeadersPresenceValidator(request_headers, response_headers, check_condition)
        self.validate(validator, path_filters=path_filter, success_by_default=True)

    def assert_headers_match(self, path_filter, request_headers=(), response_headers=(), check_condition=None):
        validator = HeadersMatchValidator(request_headers, response_headers, check_condition)
        self.validate(validator, path_filters=path_filter, success_by_default=True)

    def validate_telemetry(self, validator=None, success_by_default=False):
        self.validate(validator=validator, success_by_default=success_by_default, path_filters="/api/v2/apmtelemetry")

    def add_traces_validation(self, validator, success_by_default=False):
        self.validate(
            validator=validator, success_by_default=success_by_default, path_filters=r"/api/v0\.[1-9]+/traces"
        )
