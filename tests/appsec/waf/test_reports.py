# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
import pytest
import re

from tests.constants import PYTHON_RELEASE_GA_1_1
from utils import BaseTestCase, context, interfaces, released, irrelevant, coverage


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@released(golang="1.38.0", dotnet="2.9.0", java="0.100.0", nodejs="2.8.0", php_appsec="0.3.0", python=PYTHON_RELEASE_GA_1_1, ruby="?")
@coverage.good
class Test_Monitoring(BaseTestCase):
    """ Support In-App WAF monitoring tags and metrics  """

    expected_version_regex = r"[0-9]+\.[0-9]+\.[0-9]+"

    def test_waf_monitoring(self):
        """ WAF monitoring span tags and metrics are expected to be sent on each request """

        # Tags that are expected to be reported on every request
        expected_rules_version_tag = "_dd.appsec.event_rules.version"
        expected_waf_monitoring_meta_tags = [expected_rules_version_tag]
        expected_waf_monitoring_metrics_tags = ["_dd.appsec.waf.duration"]

        # Tags that are expected to be reported at least once at some point

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

            if re.match(self.expected_version_regex, meta[expected_rules_version_tag], 0) is None:
                raise Exception(
                    f"the span meta tag `{meta[expected_rules_version_tag]}` doesn't match the version regex"
                )

            if meta[expected_rules_version_tag] != str(context.appsec_rules_version):
                raise Exception(
                    f"the event rules version `{meta[expected_rules_version_tag]}` reported in the span tag {expected_rules_version_tag} isn't equal to the weblog context version `{context.appsec_rules_version}`"
                )

            return True

        r = self.weblog_get("/waf/", headers={"User-Agent": f"Arachni/v1"})
        interfaces.library.assert_waf_attack(r)
        interfaces.library.add_appsec_validation(r, validate_waf_monitoring_span_tags)

    def test_waf_monitoring_once(self):
        """
        Some WAF monitoring span tags and metrics are expected to be sent at
        least once in a request span at some point
        """

        # Tags that are expected to be reported at least once at some point
        expected_waf_version_tag = "_dd.appsec.waf.version"
        expected_rules_errors_meta_tag = "_dd.appsec.event_rules.errors"
        expected_rules_monitoring_nb_loaded_tag = "_dd.appsec.event_rules.loaded"
        expected_rules_monitoring_nb_errors_tag = "_dd.appsec.event_rules.error_count"
        expected_rules_monitoring_metrics_tags = [
            expected_rules_monitoring_nb_loaded_tag,
            expected_rules_monitoring_nb_errors_tag,
        ]

        def validate_rules_monitoring_span_tags(span):
            """
            Validate the mandatory rules monitoring span tags are added to a request span at some point such as the
            first request or first attack.
            """

            meta = span["meta"]
            if expected_waf_version_tag not in meta:
                return None  # Skip this span

            metrics = span["metrics"]
            for m in expected_rules_monitoring_metrics_tags:
                if m not in metrics:
                    return None  # Skip this span

            if re.match(self.expected_version_regex, meta[expected_waf_version_tag], 0) is None:
                raise Exception(f"the span meta tag `{meta[expected_waf_version_tag]}` doesn't match the version regex")

            if (
                expected_rules_monitoring_nb_loaded_tag in metrics
                and metrics[expected_rules_monitoring_nb_loaded_tag] <= 0
            ):
                raise Exception(
                    f"the number of loaded rules should be strictly positive when using the recommended rules"
                )

            if (
                expected_rules_monitoring_nb_errors_tag in metrics
                and metrics[expected_rules_monitoring_nb_errors_tag] != 0
            ):
                raise Exception(f"the number of rule errors should be 0")

            possible_errors_tag_values = ["null", "{}"]
            if (
                expected_rules_errors_meta_tag in meta
                and meta[expected_rules_errors_meta_tag] not in possible_errors_tag_values
            ):
                raise Exception(
                    f"if there's no rule errors and if there are rule errors detail, then `{expected_rules_errors_meta_tag}` should be {{}} or null but was `{meta[expected_rules_errors_meta_tag]}`"
                )

            return True

        # Perform an attack for the sake of having a request and an event in
        # order to be able to run this test alone. But the validation function
        # is not associated with the attack request.
        r = self.weblog_get("/waf/", headers={"User-Agent": f"Arachni/v1"})
        interfaces.library.assert_waf_attack(r)
        interfaces.library.add_span_validation(validator=validate_rules_monitoring_span_tags)

    @irrelevant(condition=context.library not in ["python", "golang", "dotnet", "nodejs"], reason="optional tags")
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
