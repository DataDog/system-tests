# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

""" Misc validations """

from collections import Counter

from utils.tools import m
from utils.interfaces._core import BaseValidation
from utils.interfaces._library._utils import get_root_spans, _get_rid_from_span


class _TraceIdUniqueness(BaseValidation):
    path_filters = r"/v[0-9]\.[0-9]+/traces"  # Should be implemented independently from the endpoint version

    is_success_on_expiry = False  # I need at least one value to be validated

    def __init__(self, uniqueness_exceptions):
        super().__init__()
        self.traces_ids = Counter()
        self.uniqueness_exceptions = uniqueness_exceptions

    def check(self, data):
        if not isinstance(data["request"]["content"], list):
            self.log_error(f"For {data['log_filename']}, traces shoud be an array")
            return

        for trace in data["request"]["content"]:
            if len(trace):
                span = trace[0]
                self.is_success_on_expiry = True

                if "trace_id" not in span:
                    self.set_failure(f"Can't find trace_id in request {data['log_filename']}")
                else:
                    trace_id = span["trace_id"]
                    self.traces_ids[trace_id] += 1

    def final_check(self):
        for trace_id, count in self.traces_ids.items():
            if count > 1 and self.uniqueness_exceptions.should_be_unique(trace_id):
                self.log_error(f"Found duplicate trace id {trace_id}")


class _ReceiveRequestRootTrace(BaseValidation):
    """Asserts that a trace for a request has been sent to the agent"""

    path_filters = ["/v0.4/traces"]
    is_success_on_expiry = False

    def check(self, data):
        for root_span in get_root_spans(data["request"]["content"]):
            if root_span.get("type") != "web":
                continue
            self.set_status(True)

    def set_expired(self):
        super().set_expired()
        if not self.is_success:
            self.log_error(
                f'Validation "{self.message}", nothing has been reported. No request root span with has been found'
            )


class _TracesValidation(BaseValidation):
    """ will run an arbitrary check on traces. Validator function can :
        * returns true => validation will be validated at the end (but trace will continue to be checked)
        * returns False or None => nothing is done
        * raise an exception => validation will fail
    """

    path_filters = r"/v0\.[1-9]+/traces"

    def __init__(self, validator, is_success_on_expiry):
        super().__init__()
        self.is_success_on_expiry = is_success_on_expiry
        self.validator = validator

    def check(self, data):
        try:
            if self.validator(data):
                self.log_debug(f"Trace in {data['log_filename']} validates {m(self.message)}")
                self.is_success_on_expiry = True
        except Exception as e:
            self.set_failure(f"{m(self.message)} not validated: {e}\npayload is: {data['log_filename']}")


class _SpanValidation(BaseValidation):
    """ will run an arbitrary check on spans. If a request is provided, only span
        related to this request will be checked.
        Validator function can :
        * returns true => validation will be validated at the end (but trace will continue to be checked)
        * returns False or None => nothing is done
        * raise an exception => validation will fail
    """

    path_filters = "/v0.4/traces"

    def __init__(self, request, validator):
        super().__init__(request=request)
        self.validator = validator

    def check(self, data):
        if not isinstance(data["request"]["content"], list):
            self.log_error(f"In {data['log_filename']}, traces should be an array")
            return  # do not fail, it's schema's job

        for trace in data["request"]["content"]:
            for span in trace:
                if self.rid:
                    if self.rid != _get_rid_from_span(span):
                        continue

                    self.log_debug(f"Found a trace for {m(self.message)}")

                try:
                    if self.validator(span):
                        self.log_debug(f"Trace in {data['log_filename']} validates {m(self.message)}")
                        self.is_success_on_expiry = True
                except Exception as e:
                    self.set_failure(f"{m(self.message)} not validated: {e}\nSpan is: {span}")


class _TracesValidation(BaseValidation):
    def __init__(self, request, min_trace_count=1, span_type=None, custom_traces_validation=None):
        super().__init__(request=request)
        self.min_trace_count = min_trace_count
        self.span_type = span_type
        self.custom_traces_validation = custom_traces_validation

    path_filters = "/v0.4/traces"

    def check(self, data):
        if not isinstance(data["request"]["content"], list):
            # do not fail here, it's schema's job, simply ignore it
            self.log_error(f"{data['log_filename']} content should be an array")
            return

        span_types = []

        rid_trace_ids = set()
        correlated_local_traces = []

        for trace in data["request"]["content"]:
            for span in trace:
                if self.rid == _get_rid_from_span(span):
                    rid_trace_ids.add(span["trace_id"])

        for trace in data["request"]["content"]:
            trace_is_connected = False
            for span in trace:
                if span["trace_id"] in rid_trace_ids:
                    trace_is_connected = True
                    span_types.append(span.get("type"))
            if trace_is_connected:
                correlated_local_traces.append(trace)

        validation_messages = []

        if len(correlated_local_traces) >= self.min_trace_count:
            self.log_debug(f"Traces found for  {self.message}")
            if self.custom_traces_validation is not None:
                validation_messages += self.custom_traces_validation(correlated_local_traces)
            if self.span_type is not None and self.span_type not in span_types:
                validation_messages.append(
                    f"Did not find span type '{self.span_type}' in reported span types: {span_types}"
                )

            total_errors = len(validation_messages)
            if total_errors > 0:
                final_validation_message = f"Validation messages ({total_errors}):\n - "
                final_validation_message += "\n - ".join(validation_messages)
                self.log_error(final_validation_message)
                self.log_error(f"All correlated traces:\n {str(correlated_local_traces)}")
            else:
                self.set_status(True)
        elif len(correlated_local_traces) > 0:
            self.log_info(f"Found {len(correlated_local_traces)} traces, waiting for {self.min_trace_count}")
