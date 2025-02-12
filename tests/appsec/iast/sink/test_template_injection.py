# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, weblog, rfc
from tests.appsec.iast.utils import BaseSinkTest, validate_extended_location_data


@features.iast_sink_template_injection
class TestTemplateInjection(BaseSinkTest):
    """Test template injection detection."""

    vulnerability_type = "TEMPLATE_INJECTION"
    http_method = "POST"
    insecure_endpoint = "/iast/template_injection/test_insecure"
    secure_endpoint = "/iast/template_injection/test_secure"

    data = {"template": "Hello"}


@rfc("https://docs.google.com/document/d/1R8AIuQ9_rMHBPdChCb5jRwPrg1WvIz96c_WQ3y8DWk4")
@features.iast_extended_location
class TestTemplateInjection_ExtendedLocation:
    """Test extended location data"""

    vulnerability_type = "TEMPLATE_INJECTION"

    def setup_extended_location_data(self):
        self.r = weblog.post("/iast/template_injection/test_insecure", data={"template": "Hello"})

    def test_extended_location_data(self):
        validate_extended_location_data(self.r, self.vulnerability_type)
