# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, missing_feature, interfaces, coverage, released
from utils.interfaces._library._utils import get_root_spans
from utils.interfaces._core import BaseValidation


@coverage.basic
@released(
    dotnet="?", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?", cpp="?",
)
class TestIastNoRequest(BaseTestCase):
    """ IAST deals with vulnerabilities outside of requests """

    @missing_feature(reason="Need to implement span creation")
    def test_span_creation(self):
        """ IAST creates a new span when no request is active """

        def is_iast_root_span(span):
            return span.get("type", "") == "vulnerability"

        def has_root_iast_span(iast_spans):
            root_spans = list(filter(is_iast_root_span, iast_spans))
            return len(root_spans) > 0

        interfaces.library.append_validation(_IastSpansValidation(has_root_iast_span))


class _IastSpansValidation(BaseValidation):
    """ Performs a validation on all spans with IAST metadata """

    path_filters = ["/v0.4/traces"]

    def __init__(self, validator):
        super().__init__()
        self.validator = validator
        self.iast_spans = []  # list of all spans with IAST information

    def check(self, data):
        content = data["request"]["content"]
        for i, span in enumerate(get_root_spans(content)):
            if "_dd.iast.json" in span.get("meta", {}):
                self.iast_spans.append(span)

    def final_check(self):
        try:
            self.set_status(self.validator(self.iast_spans))
        except Exception as e:
            self.set_failure(message="Failed to find matching spans", exception=e, data=self.iast_spans)
