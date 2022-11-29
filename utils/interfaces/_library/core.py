# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json
import threading

from utils.tools import logger
from utils._context.core import context
from utils.interfaces._core import InterfaceValidator, get_rid
from utils.interfaces._library._utils import _get_rid_from_span, get_rid_from_user_agent
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
    _AppHeartbeatValidation,
)
from utils.interfaces._misc_validators import HeadersPresenceValidation


class LibraryInterfaceValidator(InterfaceValidator):
    """Validate library/agent interface"""

    def __init__(self):
        super().__init__("library")
        self.ready = threading.Event()
        self.uniqueness_exceptions = _TraceIdUniquenessExceptions()

        if context.library == "java":
            self.timeout = 80
        elif context.library.library in ("golang",):
            self.timeout = 10
        elif context.library.library in ("nodejs",):
            self.timeout = 5
        elif context.library.library in ("php",):
            self.timeout = 10  # possibly something weird on obfuscator, let increase the delay for now
        elif context.library.library in ("python",):
            self.timeout = 25
        else:
            self.timeout = 40

    def append_data(self, data):
        self.ready.set()
        return super().append_data(data)

    ############################################################
    def get_traces(self, request=None):
        rid = get_rid(request)

        paths = ["/v0.4/traces", "/v0.5/traces"]

        for data in self.get_data(path_filters=paths):
            traces = data["request"]["content"]
            for trace in traces:
                if len(trace) != 0:
                    if rid is None:
                        yield data, trace
                    else:
                        first_span = trace[0]
                        span_rid = _get_rid_from_span(first_span)
                        if span_rid == rid:
                            yield data, trace

    def get_spans(self, request=None):
        for data, trace in self.get_traces(request=request):
            for span in trace:
                yield data, trace, span

    def get_appsec_events(self, request=None):
        for data, trace, span in self.get_spans(request):
            if "_dd.appsec.json" in span.get("meta", {}):
                appsec_data = json.loads(span["meta"]["_dd.appsec.json"])
                yield data, trace, span, appsec_data

    def get_legacy_appsec_events(self, request):
        paths_with_appsec_events = ["/appsec/proxy/v1/input", "/appsec/proxy/api/v2/appsecevts"]

        rid = get_rid(request)

        for data in self.get_data(path_filters=paths_with_appsec_events):
            events = data["request"]["content"]["events"]
            for event in events:
                if "trace" in event["context"] and "span" in event["context"]:

                    if rid is None:
                        yield data, event
                    else:
                        user_agents = (
                            event.get("context", {})
                            .get("http", {})
                            .get("request", {})
                            .get("headers", {})
                            .get("user-agent", [])
                        )

                        # version 1 of appsec events schema
                        if isinstance(user_agents, str):
                            user_agents = [
                                user_agents,
                            ]

                        for user_agent in user_agents:
                            if get_rid_from_user_agent(user_agent) == rid:
                                yield data, event
                                break

    ############################################################

    def validate_appsec(self, request, validator, success_by_default=False, legacy_validator=None):
        for data, _, span, appsec_data in self.get_appsec_events(request=request):

            if request:  # do not spam log if all data are sent to the validator
                logger.debug(f"Try to find relevant appsec data in {data['log_filename']}; span #{span['span_id']}")

            if validator(span, appsec_data):
                return

        if legacy_validator:
            for data, event in self.get_legacy_appsec_events(request=request):
                if request:  # do not spam log if all data are sent to the validator
                    logger.debug(f"Try to find relevant appsec data in {data['log_filename']}")

                    if validator(event):
                        return

        if not success_by_default:
            raise Exception("No appsec event has been found")

    ######################################################

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
        validator = _WafAttack(
            rule=rule, pattern=pattern, value=value, address=address, patterns=patterns, key_path=key_path,
        )

        self.validate_appsec(
            request, validator=validator.validate, legacy_validator=validator.validate_legacy, success_by_default=False,
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

    def assert_app_heartbeat_validation(self):
        self.append_validation(_AppHeartbeatValidation())

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
