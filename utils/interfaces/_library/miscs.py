# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Misc validations"""

import re


class _SpanTagValidator:
    """will run an arbitrary check on spans. If a request is provided, only span"""

    path_filters = ["/v0.4/traces", "/v0.5/traces"]

    def __init__(self, tags: dict | None, *, value_as_regular_expression: bool):
        self.tags = {} if tags is None else tags
        self.value_as_regular_expression = value_as_regular_expression

    def __call__(self, span: dict):
        for tag_key in self.tags:
            if tag_key not in span["meta"]:
                raise ValueError(f"{tag_key} tag not found in span's meta")

            expect_value = self.tags[tag_key]
            actual_value = span["meta"][tag_key]

            if self.value_as_regular_expression:
                if not re.compile(expect_value).fullmatch(actual_value):
                    raise ValueError(
                        f'{tag_key} tag value is "{actual_value}", and should match regex "{expect_value}"'
                    )
            elif expect_value != actual_value:
                raise ValueError(f'{tag_key} tag in span\'s meta should be "{expect_value}", not "{actual_value}"')

        return True
