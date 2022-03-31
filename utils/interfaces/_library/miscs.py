# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

""" Misc validations """

from collections import Counter

from utils.tools import m
from utils.interfaces._core import BaseValidation
from utils.interfaces._library._utils import get_root_spans, _get_rid_from_span


def _get_spans_by_rid(rid, data):
    trace_ids = set()
    for trace in data["request"]["content"]:
        for span in trace:
            if rid == _get_rid_from_span(span):
                trace_ids.add(span["trace_id"])

    for trace in data["request"]["content"]:
        for span in trace:
            if span["trace_id"] in trace_ids:
                yield span


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


class _TraceExistence(BaseValidation):
    def __init__(self, request, span_type=None):
        super().__init__(request=request)
        self.span_type = span_type

    path_filters = "/v0.4/traces"

    def check(self, data):
        if not isinstance(data["request"]["content"], list):
            # do not fail here, it's schema's job, simply ignore it
            self.log_error(f"{data['log_filename']} content should be an array")
            return

        check_pass = False
        span_types = []
        span_count = len(span_types)

        for span in _get_spans_by_rid(self.rid, data):
            span_count = span_count + 1
            if (not hasattr(span, "type")):
                self.log_error("Span is missing type attribute --> {0}".format(span))
            else:
                span_types.append(span["type"])
                if self.span_type is None or self.span_type == span["type"]:
                    check_pass = True

        if check_pass:
            self.log_debug(f"Found a trace for {self.message}")
            self.set_status(True)
        elif span_count > 0:
            log_messages = []
            log_messages.append(f"Expected span with rid {self.rid} and span type {self.span_type}")
            log_messages.append(f"Found {span_count} spans with matching rid")
            span_types_message = ", ".join(span_types)
            log_messages.append(f"Span types found: {span_types_message}")
            self.log_error("\n".join(log_messages))
