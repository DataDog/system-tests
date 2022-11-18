# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json

import pytest

from tests.constants import PYTHON_RELEASE_GA_1_1
from utils import BaseTestCase, context, interfaces, released, scenario

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@released(
    golang="1.38.0",
    dotnet="2.7.0",
    java="0.100.0",
    nodejs="2.8.0",
    php_appsec="0.3.0",
    python=PYTHON_RELEASE_GA_1_1,
    ruby="?",
)
@scenario("APPSEC_RULES_MONITORING_WITH_ERRORS")
class Test_Monitoring(BaseTestCase):
    """ Support In-App WAF monitoring tags and metrics  """

    def test_waf_monitoring(self):
        """
        Some WAF monitoring span tags and metrics are expected to be sent at
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

        def validate_rules_monitoring_span_tags(span):
            """
            Validate the mandatory rules monitoring span tags are added to a request span at some point such as the
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
        r = self.weblog_get("/waf/", params={"v": ".htaccess"})
        interfaces.library.assert_waf_attack(r)
        interfaces.library.add_span_validation(validator=validate_rules_monitoring_span_tags)
