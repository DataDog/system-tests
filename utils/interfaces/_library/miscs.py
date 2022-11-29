# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

""" Misc validations """

import re

from utils.tools import m
from utils.interfaces._core import BaseValidation, get_rid_from_span


class _SpanTagValidation(BaseValidation):
    """will run an arbitrary check on spans. If a request is provided, only span"""

    path_filters = ["/v0.4/traces", "/v0.5/traces"]

    def __init__(self, request, tags, value_as_regular_expression):
        super().__init__(request=request)
        self.tags = {} if tags is None else tags
        self.value_as_regular_expression = value_as_regular_expression

    def check(self, data):
        if not isinstance(data["request"]["content"], list):
            self.log_error(f"In {data['log_filename']}, traces should be an array")
            return  # do not fail, it's schema's job

        for trace in data["request"]["content"]:
            for span in trace:
                if self.rid:
                    if self.rid != get_rid_from_span(span):
                        continue

                    self.log_debug(f"Found a trace for {m(self.message)}")

                try:
                    for tagKey in self.tags:
                        if tagKey not in span["meta"]:
                            raise Exception(f"{tagKey} tag not found in span's meta")

                        expectValue = self.tags[tagKey]
                        actualValue = span["meta"][tagKey]

                        if self.value_as_regular_expression:
                            if not re.compile(expectValue).fullmatch(actualValue):
                                raise Exception(
                                    f'{tagKey} tag value is "{actualValue}", and should match regex "{expectValue}"'
                                )
                        else:
                            if expectValue != actualValue:
                                raise Exception(
                                    f'{tagKey} tag in span\'s meta should be "{expectValue}", not "{actualValue}"'
                                )

                    self.log_debug(f"Trace in {data['log_filename']} validates {m(self.message)}")
                    self.is_success_on_expiry = True
                except Exception as exc:
                    self.set_failure(exception=exc, data=data, extra_info=span)
