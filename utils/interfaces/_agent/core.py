# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""
This files will validate data flow between agent and backend
"""

import threading

from utils.interfaces._core import BaseValidation, InterfaceValidator
from utils.interfaces._schemas_validators import SchemaValidator
from utils.interfaces._library.telemetry import (
    _TelemetryRequestSuccessValidation,
    TELEMETRY_INTAKE_ENDPOINT,
)
from utils.interfaces._profiling import _ProfilingValidation, _ProfilingFieldAssertion
from utils.interfaces._agent.appsec import AppSecValidation
from utils.interfaces._misc_validators import HeadersPresenceValidation


class AgentInterfaceValidator(InterfaceValidator):
    """Validate agent/backend interface"""

    def __init__(self):
        super().__init__("agent")
        self.ready = threading.Event()
        self.expected_timeout = 5

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

    def assert_telemetry_requests_are_successful(self):
        self.append_validation(_TelemetryRequestSuccessValidation(TELEMETRY_INTAKE_ENDPOINT))

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
