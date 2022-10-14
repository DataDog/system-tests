# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import threading

from utils.interfaces._core import InterfaceValidator
from utils.interfaces._schemas_validators import SchemaValidator

from utils.interfaces._library.appsec import _NoAppsecEvent, _WafAttack, _AppSecValidation, _ReportedHeader
from utils.interfaces._library.appsec_iast import _AppSecIastValidation, _NoIastEvent

from utils.interfaces._profiling import _ProfilingFieldAssertion
from utils.interfaces._library.metrics import _MetricAbsence, _MetricExistence
from utils.interfaces._library.miscs import (
    _TraceIdUniqueness,
    _ReceiveRequestRootTrace,
    _SpanValidation,
    _SpanTagValidation,
    _TraceExistence,
)
from utils.interfaces._library.sampling import (
    _TracesSamplingDecision,
    _AllRequestsTransmitted,
    _AddSamplingDecisionValidation,
    _DistributedTracesDeterministicSamplingDecisisonValidation,
)
from utils.interfaces._library.telemetry import (
    _SeqIdLatencyValidation,
    _NoSkippedSeqId,
)
from utils.interfaces._misc_validators import HeadersPresenceValidation


class LibraryInterfaceValidator(InterfaceValidator):
    """Validate library/agent interface"""

    def __init__(self):
        super().__init__("library")
        self.ready = threading.Event()
        self.uniqueness_exceptions = _TraceIdUniquenessExceptions()

    def get_expected_timeout(self, context):
        result = 40

        if context.library == "java":
            result = 80
        elif context.library.library in ("golang",):
            result = 10
        elif context.library.library in ("nodejs",):
            result = 5
        elif context.library.library in ("php",):
            result = 10  # possibly something weird on obfuscator, let increase the delay for now
        elif context.library.library in ("python",):
            result = 25

        return max(result, self._minimal_expected_timeout)

    def append_data(self, data):
        self.ready.set()
        return super().append_data(data)

    def assert_headers_presence(self, path_filter, request_headers=(), response_headers=(), check_condition=None):
        self.append_validation(
            HeadersPresenceValidation(path_filter, request_headers, response_headers, check_condition)
        )

    def assert_receive_request_root_trace(self):
        self.append_validation(_ReceiveRequestRootTrace())

    def assert_schemas(self, allowed_errors=None):
        self.append_validation(SchemaValidator("library", allowed_errors))

    def assert_sampling_decision_respected(self, sampling_rate):
        self.append_validation(_TracesSamplingDecision(sampling_rate))

    def assert_all_traces_requests_forwarded(self, paths):
        self.append_validation(_AllRequestsTransmitted(paths))

    def assert_trace_id_uniqueness(self):
        self.append_validation(_TraceIdUniqueness(self.uniqueness_exceptions))

    def assert_sampling_decisions_added(self, traces):
        self.append_validation(_AddSamplingDecisionValidation(traces))

    def assert_deterministic_sampling_decisions(self, traces):
        self.append_validation(_DistributedTracesDeterministicSamplingDecisisonValidation(traces))

    def assert_no_appsec_event(self, request):
        self.append_validation(_NoAppsecEvent(request))

    def assert_waf_attack(
        self, request, rule=None, pattern=None, value=None, address=None, patterns=None, key_path=None
    ):
        self.append_validation(
            _WafAttack(
                request, rule=rule, pattern=pattern, value=value, address=address, patterns=patterns, key_path=key_path
            )
        )

    def assert_metric_existence(self, metric_name):
        self.append_validation(_MetricExistence(metric_name))

    def assert_metric_absence(self, metric_name):
        self.append_validation(_MetricAbsence(metric_name))

    def add_traces_validation(self, validator, is_success_on_expiry=False):
        self.add_validation(
            validator=validator, is_success_on_expiry=is_success_on_expiry, path_filters=r"/v0\.[1-9]+/traces"
        )

    def add_span_validation(self, request=None, validator=None, is_success_on_expiry=False):
        self.append_validation(
            _SpanValidation(request=request, validator=validator, is_success_on_expiry=is_success_on_expiry)
        )

    def add_span_tag_validation(self, request=None, tags=None, value_as_regular_expression=False):
        self.append_validation(
            _SpanTagValidation(request=request, tags=tags, value_as_regular_expression=value_as_regular_expression)
        )

    def add_appsec_validation(self, request=None, validator=None, legacy_validator=None, is_success_on_expiry=False):
        self.append_validation(
            _AppSecValidation(
                request=request,
                validator=validator,
                legacy_validator=legacy_validator,
                is_success_on_expiry=is_success_on_expiry,
            )
        )

    def expect_iast_vulnerabilities(
        self,
        request,
        vulnerability_type=None,
        location_path=None,
        location_line=None,
        evidence=None,
        vulnerability_count=None,
    ):
        self.append_validation(
            _AppSecIastValidation(
                request=request,
                vulnerability_type=vulnerability_type,
                location_path=location_path,
                location_line=location_line,
                evidence=evidence,
                vulnerability_count=vulnerability_count,
            )
        )

    def expect_no_vulnerabilities(self, request):
        self.append_validation(_NoIastEvent(request=request))

    def add_telemetry_validation(self, validator, is_success_on_expiry=False):
        self.add_validation(
            validator=validator,
            is_success_on_expiry=is_success_on_expiry,
            path_filters="/telemetry/proxy/api/v2/apmtelemetry",
        )

    def add_appsec_reported_header(self, request, header_name):
        self.append_validation(_ReportedHeader(request, header_name))

    def assert_seq_ids_are_roughly_sequential(self):
        self.append_validation(_SeqIdLatencyValidation())

    def assert_no_skipped_seq_ids(self):
        self.append_validation(_NoSkippedSeqId())

    def add_profiling_validation(self, validator):
        self.add_validation(validator, path_filters="/profiling/v1/input")

    def profiling_assert_field(self, field_name, content_pattern=None):
        self.append_validation(_ProfilingFieldAssertion(field_name, content_pattern))

    def assert_trace_exists(self, request, span_type=None):
        self.append_validation(_TraceExistence(request=request, span_type=span_type))

    def add_remote_configuration_validation(self, validator, is_success_on_expiry=False):
        self.add_validation(validator, is_success_on_expiry=is_success_on_expiry, path_filters=r"/v\d+.\d+/config")


class _TraceIdUniquenessExceptions:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.traces_ids = set()

    def add_trace_id(self, trace_id):
        with self._lock:
            self.traces_ids.add(trace_id)

    def should_be_unique(self, trace_id):
        with self._lock:
            return trace_id not in self.traces_ids
