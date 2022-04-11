# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, context, interfaces, released, bug, irrelevant, missing_feature, flaky, rfc
import pytest
import re


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@missing_feature(library="golang")
@missing_feature(library="java")
@missing_feature(library="dotnet")
@missing_feature(library="nodejs")
@missing_feature(library="php")
@missing_feature(library="python")
@missing_feature(library="ruby")
class Test_Metrics(BaseTestCase):
    """ Support In-App WAF monitoring tags and metrics  """

    def test_waf_monitoring(self):
        """ WAF monitoring span tags and metrics are expected to be sent on each request """

        # Tags that are expected to be reported on every request
        expected_rules_version_tag = "_dd.appsec.event_rules.version"
        expected_waf_monitoring_meta_tags = [expected_rules_version_tag]
        expected_waf_monitoring_metrics_tags = ["_dd.appsec.waf.duration"]

        # Tags that are expected to be reported at least once at some point
        expected_waf_version_tag = "_dd.appsec.waf.version"
        expected_rules_monitoring_meta_tags = [expected_waf_version_tag, "_dd.appsec.event_rules.errors"]
        expected_rules_monitoring_metrics_tags = ["_dd.appsec.event_rules.loaded", "_dd.appsec.event_rules.error_count"]
        expected_version_regex = r"[0-9]+\.[0-9]+\.[0-9]+"

        def validate_waf_monitoring_span_tags(span, appsec_data):
            """ Validate the mandatory waf monitoring span tags are added to the request span having an attack """

            meta = span["meta"]
            for m in expected_waf_monitoring_meta_tags:
                if m not in meta:
                    raise Exception(f"missing span meta tag `{m}` in {meta}")

            metrics = span["metrics"]
            for m in expected_waf_monitoring_metrics_tags:
                if m not in metrics:
                    raise Exception(f"missing span metric tag `{m}` in {metrics}")

            if re.match(expected_version_regex, meta[expected_rules_version_tag], 0) is None:
                raise Exception(
                    f"the span meta tag `{meta[expected_rules_version_tag]}` doesn't match the version regex"
                )

            if meta[expected_rules_version_tag] != str(context.appsec_rules_version):
                raise Exception(
                    f"the event rules version `{meta[expected_rules_version_tag]}` reported in the span tag {expected_rules_version_tag} isn't equal to the weblog context version `{context.appsec_rules_version}`"
                )

            return True

        def validate_rules_monitoring_span_tags(span):
            """
            Validate the mandatory rules monitoring span tags are added to a request span at some point such as the
            first request or first attack.
            """

            meta = span["meta"]
            for m in expected_rules_monitoring_meta_tags:
                if m not in meta:
                    raise Exception(f"missing span meta tag `{m}` in {meta}")

            metrics = span["metrics"]
            for m in expected_rules_monitoring_metrics_tags:
                if m not in metrics:
                    raise Exception(f"missing span metric tag `{m}` in {metrics}")

            if re.match(expected_version_regex, meta[expected_waf_version_tag], 0) is None:
                raise Exception(f"the span meta tag `{meta[expected_waf_version_tag]}` doesn't match the version regex")

            return True

        r = self.weblog_get("/waf/", headers={"User-Agent": f"Arachni/v1"})
        interfaces.library.assert_waf_attack(r)
        interfaces.library.add_appsec_validation(r, validate_waf_monitoring_span_tags)
        interfaces.library.add_span_validation(r, validate_rules_monitoring_span_tags)

    @irrelevant(condition=context.library not in ["golang"], reason="optional tags")
    def test_waf_monitoring_optional(self):
        """ WAF monitoring span tags and metrics may send extra optional tags """

        expected_waf_duration_metric = "_dd.appsec.waf.duration"
        expected_bindings_duration_metric = "_dd.appsec.waf.duration_ext"
        expected_metrics_tags = [expected_waf_duration_metric, expected_bindings_duration_metric]

        def validate_waf_span_tags(span, appsec_data):
            metrics = span["metrics"]
            for m in expected_metrics_tags:
                if m not in metrics:
                    raise Exception(f"missing span metric tag `{m}` in {metrics}")

            if metrics[expected_bindings_duration_metric] < metrics[expected_waf_duration_metric]:
                raise Exception(
                    f"unexpected waf duration metrics: the overall execution duration (with bindings) `{metrics[expected_bindings_duration_metric]}` is less than the internal waf duration `{metrics[expected_waf_duration_metric]}`"
                )

            return True

        r = self.weblog_get("/waf/", headers={"User-Agent": f"Arachni/v1"})
        interfaces.library.assert_waf_attack(r)
        interfaces.library.add_appsec_validation(r, validate_waf_span_tags)
