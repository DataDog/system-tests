# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""
This files will validate data flow between agent and backend
"""

import threading

from utils.interfaces._core import BaseValidation, InterfaceValidator
from utils.interfaces._schemas_validators import SchemaValidator
from utils.interfaces._profiling import _ProfilingValidation, _ProfilingFieldAssertion
from utils.interfaces._agent.appsec import AppSecValidation
from utils.interfaces._agent.telemetry import _TelemetryValidation
from utils.interfaces._misc_validators import HeadersPresenceValidation, HeadersMatchValidation
from utils.tools import m


class AgentInterfaceValidator(InterfaceValidator):
    """Validate agent/backend interface"""

    def __init__(self):
        super().__init__("agent")
        self.ready = threading.Event()

    def get_expected_timeout(self, context):
        return max(5, self._minimal_expected_timeout)

    def append_data(self, data):
        data = super().append_data(data)

        self.ready.set()

        return data

    def assert_use_domain(self, domain):
        self.append_validation(_UseDomain(domain))

    def assert_schemas(self, allowed_errors=None):
        self.append_validation(SchemaValidator("agent", allowed_errors))

    def assert_metric_existence(self, metric_name):
        self.append_validation(_MetricExistence(metric_name))

    def add_profiling_validation(self, validator):
        self.append_validation(_ProfilingValidation(validator))

    def profiling_assert_field(self, field_name, content_pattern=None):
        self.append_validation(_ProfilingFieldAssertion(field_name, content_pattern))

    def add_appsec_validation(self, request, validator):
        self.append_validation(AppSecValidation(request, validator))

    def assert_headers_presence(self, path_filter, request_headers=(), response_headers=(), check_condition=None):
        self.append_validation(
            HeadersPresenceValidation(path_filter, request_headers, response_headers, check_condition)
        )

    def assert_headers_match(self, path_filter, request_headers=(), response_headers=(), check_condition=None):
        self.append_validation(HeadersMatchValidation(path_filter, request_headers, response_headers, check_condition))

    def add_telemetry_validation(self, validator=None, is_success_on_expiry=False):
        self.append_validation(_TelemetryValidation(validator=validator, is_success_on_expiry=is_success_on_expiry))

    def add_traces_validation(self, validator, is_success_on_expiry=False):
        self.append_validation(_TracesValidation(validator=validator, is_success_on_expiry=is_success_on_expiry))


class _UseDomain(BaseValidation):
    is_success_on_expiry = True

    def __init__(self, domain):
        super().__init__()
        self.domain = domain

    def check(self, data):
        domain = data["host"][-len(self.domain) :]

        if domain != self.domain:
            self.set_failure(f"Message #{data['log_filename']} uses host {domain} instead of {self.domain}")


class _MetricExistence(BaseValidation):
    path_filters = "/api/v0.2/traces"

    def __init__(self, metric_name):
        super().__init__()
        self.metric_name = metric_name

    def check(self, data):
        for trace in data["request"]["content"]["traces"]:
            for span in trace["spans"]:
                if "metrics" in span and self.metric_name in span["metrics"]:
                    self.set_status(True)
                    break


class _TracesValidation(BaseValidation):
    """will run an arbitrary check on traces. Validator function can :
    * returns true => validation will be validated at the end (but trace will continue to be checked)
    * returns False or None => nothing is done
    * raise an exception => validation will fail
    """

    path_filters = r"/api/v0\.[1-9]+/traces"

    def __init__(self, validator, is_success_on_expiry):
        super().__init__()
        self.is_success_on_expiry = is_success_on_expiry
        self.validator = validator

    def check(self, data):
        try:
            if self.validator(data):
                self.log_debug(f"Trace in {data['log_filename']} validates {m(self.message)}")
                self.is_success_on_expiry = True
        except Exception as exc:
            self.set_failure(exception=exc, data=data, extra_info=data)
