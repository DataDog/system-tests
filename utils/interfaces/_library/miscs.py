# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

""" Misc validations """

import re


class _SpanTagValidator:
    """will run an arbitrary check on spans. If a request is provided, only span"""

    path_filters = ["/v0.4/traces", "/v0.5/traces"]

    def __init__(self, tags, value_as_regular_expression):
        self.tags = {} if tags is None else tags
        self.value_as_regular_expression = value_as_regular_expression

    def __call__(self, span):
        for tagKey in self.tags:
            print(span["meta"])
            if tagKey not in span["meta"]:
                raise ValueError(f"{tagKey} tag not found in span's meta")

            expectValue = self.tags[tagKey]
            actualValue = span["meta"][tagKey]

            if self.value_as_regular_expression:
                if not re.compile(expectValue).fullmatch(actualValue):
                    raise ValueError(f'{tagKey} tag value is "{actualValue}", and should match regex "{expectValue}"')
            else:
                if expectValue != actualValue:
                    raise ValueError(f'{tagKey} tag in span\'s meta should be "{expectValue}", not "{actualValue}"')

        return True
