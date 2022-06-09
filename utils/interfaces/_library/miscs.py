# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

""" Misc validations """

import re

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

    def __init__(self, request, validator, is_success_on_expiry):
        super().__init__(request=request)
        self.validator = validator
        self.is_success_on_expiry = is_success_on_expiry

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


class _SpanTagValidation(BaseValidation):
    """ will run an arbitrary check on spans. If a request is provided, only span
    """

    path_filters = "/v0.4/traces"

    def __init__(self, request, tags, value_as_regular_expression):
        super().__init__(request=request)
        self.tags = tags
        self.value_as_regular_expression = value_as_regular_expression

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
                    for tagKey in self.tags:
                        if tagKey not in span["meta"]:
                            raise Exception(f"{tagKey} tag not found in span's meta")

                        expectValue = self.tags[tagKey]
                        actualValue = span["meta"][tagKey]

                        match = False
                        if self.value_as_regular_expression:
                            expectRE = re.compile(expectValue)
                            if expectRE.match(actualValue):
                                match = True
                        else:
                            if expectValue == actualValue:
                                match = True

                        if not match:
                            raise Exception(
                                f'{tagKey} tag in span\'s meta should be "{expectValue}", not "{actualValue}"'
                            )

                    self.log_debug(f"Trace in {data['log_filename']} validates {m(self.message)}")
                    self.is_success_on_expiry = True
                except Exception as e:
                    self.set_failure(
                        f"{m(self.message)} not validated in {data['log_filename']}:\n{e}\nSpan is: {span}"
                    )


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

        diagnostics = ["Diagnostics:"]
        span_types = []
        span_count = len(span_types)

        for trace in data["request"]["content"]:
            for span in trace:
                if self.rid == _get_rid_from_span(span):
                    for correlated_span in trace:
                        span_count = span_count + 1
                        span_types.append(correlated_span.get("type"))
                        diagnostics.append(str(correlated_span))
                    continue

        if span_count > 0:
            if self.span_type is None:
                self.log_debug(f"Found a trace for {self.message}")
                self.set_status(True)
            elif self.span_type in span_types:
                self.log_debug(f"Found a span with type {self.span_type}")
                self.set_status(True)
            else:
                self.log_error(f"Did not find span type '{self.span_type}' in reported span types: {span_types}")
                self.log_error("\n".join(diagnostics))
