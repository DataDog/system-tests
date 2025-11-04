# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
import re
import json

from utils import weblog, context, interfaces, irrelevant, scenarios, features, bug


@features.support_in_app_waf_metrics_report
class Test_Monitoring:
    """Support In-App WAF monitoring tags and metrics"""

    expected_version_regex = r"[0-9]+\.[0-9]+\.[0-9]+"

    def setup_waf_monitoring(self):
        self.r = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def test_waf_monitoring(self):
        """WAF monitoring span tags and metrics are expected to be sent on each request"""

        # Tags that are expected to be reported on every request
        expected_rules_version_tag = "_dd.appsec.event_rules.version"
        expected_waf_monitoring_meta_tags = [expected_rules_version_tag]
        expected_waf_monitoring_metrics_tags = ["_dd.appsec.waf.duration"]

        # Tags that are expected to be reported at least once at some point

        def validate_waf_monitoring_span_tags(span: dict, appsec_data: dict):  # noqa: ARG001
            """Validate the mandatory waf monitoring span tags are added to the request span having an attack"""

            meta = span["meta"]
            for m in expected_waf_monitoring_meta_tags:
                assert m in meta, f"missing span meta tag `{m}` in meta"

            metrics = span["metrics"]
            for m in expected_waf_monitoring_metrics_tags:
                assert m in metrics, f"missing span metric tag `{m}` in metrics"

            if re.match(self.expected_version_regex, meta[expected_rules_version_tag], 0) is None:
                raise ValueError(
                    f"the span meta tag `{meta[expected_rules_version_tag]}` doesn't match the version regex"
                )

            return True

        interfaces.library.assert_waf_attack(self.r)
        interfaces.library.validate_one_appsec(self.r, validate_waf_monitoring_span_tags)

    def setup_waf_monitoring_once(self):
        self.r_once = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    @irrelevant(context.library >= "golang@v2.1.0-dev", reason="replaced by test_waf_monitoring_once_rfc1025")
    @irrelevant(context.library >= "nodejs@5.58.0", reason="replaced by test_waf_monitoring_once_rfc1025")
    @irrelevant(library="ruby", reason="replaced by test_waf_monitoring_once_rfc1025")
    def test_waf_monitoring_once(self):
        """Some WAF monitoring span tags and metrics are expected to be sent at
        least once in a request span at some point. The metrics asserted by this
        test are deprecated for libraries that implemented RFC-1025; at which
        point the test_waf_monitoring_once_rfc1025 is sufficient and this can be
        reported as irrelevant.
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

        def validate_rules_monitoring_span_tags(span: dict):
            """Validate the mandatory rules monitoring span tags are added to a request span at some point such as the
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
                    "the number of loaded rules should be strictly positive when using the recommended rules"
                )

            num_errors = metrics.get(expected_rules_monitoring_nb_errors_tag, 0)
            if num_errors == 0:
                possible_errors_tag_values = ["null", "{}"]
                if (
                    expected_rules_errors_meta_tag in meta
                    and meta[expected_rules_errors_meta_tag] not in possible_errors_tag_values
                ):
                    raise Exception(
                        "if there's no rule errors and if there are rule errors detail, then "
                        f"`{expected_rules_errors_meta_tag}` should be {{}} or null but was "
                        f"`{meta[expected_rules_errors_meta_tag]}`"
                    )
            else:
                if expected_rules_errors_meta_tag not in meta:
                    raise Exception("if there are rule errors, there should be rule error details too")
                try:
                    json.loads(meta[expected_rules_errors_meta_tag])
                except ValueError as e:
                    raise Exception(
                        f"rule error details should be valid JSON but was `{meta[expected_rules_errors_meta_tag]}`"
                    ) from e

            return True

        # Perform an attack for the sake of having a request and an event in
        # order to be able to run this test alone. But the validation function
        # is not associated with the attack request.
        interfaces.library.assert_waf_attack(self.r_once)
        interfaces.library.validate_one_span(validator=validate_rules_monitoring_span_tags)

    def setup_waf_monitoring_once_rfc1025(self):
        self.r_once = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def test_waf_monitoring_once_rfc1025(self):
        """Some WAF monitoring span tags are expected to be sent at least once
        in a request span at some point.
        """

        # Tags that are expected to be reported at least once at some point
        expected_waf_version_tag = "_dd.appsec.waf.version"

        def validate_rules_monitoring_span_tags(span: dict):
            """Validate the mandatory rules monitoring span tags are added to a request span at some point such as the
            first request or first attack.
            """

            meta = span["meta"]
            if expected_waf_version_tag not in meta:
                return None  # Skip this span

            if re.match(self.expected_version_regex, meta[expected_waf_version_tag], 0) is None:
                raise Exception(f"the span meta tag `{meta[expected_waf_version_tag]}` doesn't match the version regex")

            return True

        # Perform an attack for the sake of having a request and an event in
        # order to be able to run this test alone. But the validation function
        # is not associated with the attack request.
        interfaces.library.assert_waf_attack(self.r_once)
        interfaces.library.validate_one_span(validator=validate_rules_monitoring_span_tags)

    def setup_waf_monitoring_optional(self):
        self.r_optional = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    @irrelevant(condition=context.library not in ["python", "golang", "dotnet", "nodejs"], reason="optional tags")
    def test_waf_monitoring_optional(self):
        """WAF monitoring span tags and metrics may send extra optional tags"""

        expected_waf_duration_metric = "_dd.appsec.waf.duration"
        expected_bindings_duration_metric = "_dd.appsec.waf.duration_ext"
        expected_metrics_tags = [expected_waf_duration_metric, expected_bindings_duration_metric]

        def validate_waf_span_tags(span: dict, appsec_data: dict):  # noqa: ARG001
            metrics = span["metrics"]
            for m in expected_metrics_tags:
                if m not in metrics:
                    raise Exception(f"missing span metric tag `{m}` in {metrics}")

            if metrics[expected_bindings_duration_metric] < metrics[expected_waf_duration_metric]:
                raise Exception(
                    "unexpected waf duration metrics: the overall execution duration (with bindings) "
                    f"`{metrics[expected_bindings_duration_metric]}` is less than the internal "
                    f"waf duration `{metrics[expected_waf_duration_metric]}`"
                )

            return True

        interfaces.library.assert_waf_attack(self.r_optional)
        interfaces.library.validate_one_appsec(self.r_optional, validate_waf_span_tags)

    def setup_waf_monitoring_errors(self):
        self.r_errors = weblog.get("/waf/", params={"v": ".htaccess"})

    @scenarios.appsec_rules_monitoring_with_errors
    @bug(library="golang", reason="LANGPLAT-584")
    @irrelevant(context.library >= "nodejs@5.58.0", reason="expected tags were deprecated by rfc1025")
    @irrelevant(library="ruby", reason="replaced by test_waf_monitoring_once_rfc1025")
    def test_waf_monitoring_errors(self):
        """Some WAF monitoring span tags and metrics are expected to be sent at
        least once in a request span at some point
        """

        # Tags that are expected to be reported at least once at some point with
        # the rules details
        expected_rules_monitoring_error_details_tag = "_dd.appsec.event_rules.errors"
        expected_rules_monitoring_nb_loaded_tag = "_dd.appsec.event_rules.loaded"
        expected_rules_monitoring_nb_errors_tag = "_dd.appsec.event_rules.error_count"
        expected_rules_monitoring_meta_tags = [
            expected_rules_monitoring_error_details_tag,
        ]
        expected_rules_monitoring_metrics_tags = [
            expected_rules_monitoring_nb_loaded_tag,
            expected_rules_monitoring_nb_errors_tag,
        ]
        expected_nb_loaded = 4
        expected_nb_errors = 2
        expected_error_details = {"missing key 'name'": ["missing-name"], "missing key 'tags'": ["missing-tags"]}

        def validate_rules_monitoring_span_tags(span: dict):
            """Validate the mandatory rules monitoring span tags are added to a request span at some point such as the
            first request or first attack.
            """

            meta = span["meta"]
            for m in expected_rules_monitoring_meta_tags:
                if m not in meta:
                    return None  # Skip this span

            metrics = span["metrics"]
            for m in expected_rules_monitoring_metrics_tags:
                if m not in metrics:
                    return None  # Skip this span

            if metrics[expected_rules_monitoring_nb_loaded_tag] != expected_nb_loaded:
                raise Exception(
                    f"the number of loaded rules should be {expected_nb_loaded} but is "
                    f"`{metrics[expected_rules_monitoring_nb_loaded_tag]}`"
                )

            if metrics[expected_rules_monitoring_nb_errors_tag] != expected_nb_errors:
                raise Exception(
                    f"the number of rule errors should be {expected_nb_errors} but is "
                    f"`{metrics[expected_rules_monitoring_nb_errors_tag]}`"
                )

            # Parse the errors meta tag as json
            errors = json.loads(meta[expected_rules_monitoring_error_details_tag])
            if errors != expected_error_details:
                raise Exception(
                    f"unexpected span tag {expected_rules_monitoring_error_details_tag} value: "
                    f"got {errors} instead of {expected_error_details}"
                )

            return True

        # Perform an attack for the sake of having a request and an event in
        # order to be able to run this test alone. But the validation function
        # is not associated with the attack request.
        interfaces.library.assert_waf_attack(self.r_errors)
        interfaces.library.validate_one_span(validator=validate_rules_monitoring_span_tags)
