# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, context, interfaces, released, bug, irrelevant, missing_feature, flaky, rfc
import pytest
import re


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@released(golang="1.38.0")
@released(java="0.98.0")
@missing_feature(library="dotnet")
@missing_feature(library="nodejs")
@missing_feature(library="php")
@missing_feature(library="python")
@missing_feature(library="ruby")
class Test_Metrics(BaseTestCase):
    """ Support In-App WAF monitoring tags and metrics  """

    def test_request_data(self):
        """ WAF monitoring span tags and metrics are expected to be sent on each request """

        expected_waf_version_tag = "_dd.appsec.event_rules.version"
        expected_meta_tags = [expected_waf_version_tag]
        expected_waf_duration_metric = "_dd.appsec.waf.duration"
        expected_bindings_duration_metric = "_dd.appsec.waf.duration_ext"
        expected_metrics_tags = [expected_waf_duration_metric, expected_bindings_duration_metric]

        def validate_appsec_span_tags(span, appsec_data):
            meta = span["meta"]
            for m in expected_meta_tags:
                if m not in meta:
                    raise Exception(f"missing span meta tag `{m}` in {meta}")

            metrics = span["metrics"]
            for m in expected_metrics_tags:
                if m not in metrics:
                    raise Exception(f"missing span metric tag `{m}` in {meta}")

            if metrics[expected_bindings_duration_metric] < metrics[expected_waf_duration_metric]:
                raise Exception(
                    f"unexpected waf duration metrics: the overall execution duration (with bindings) `{metrics[expected_bindings_duration_metric]}` is less than the internal waf duration `{metrics[expected_waf_duration_metric]}`"
                )

            if re.match(r"[0-9]+\.[0-9]+\.[0-9]+", meta[expected_waf_version_tag], 0) is None:
                raise Exception(f"the span meta tag `{meta[expected_waf_version_tag]}` doesn't match the version regex")

            return True

        r = self.weblog_get("/waf/", headers={"User-Agent": f"Arachni/v1"})
        interfaces.library.assert_waf_attack(r)
        interfaces.library.add_appsec_validation(r, validate_appsec_span_tags)

    def test_request_data_once(self):
        """ WAF monitoring span tags and metrics are expected to be sent at least once at some point """

        interfaces.library.append_not_implemented_validation()
