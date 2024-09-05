# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, context, flaky
from ..utils import BaseSinkTestWithoutTelemetry


@features.iast_sink_xpathinjection
@flaky(context.library >= "dotnet@2.54.0", reason="APPSEC-54151")
class TestXPathInjection(BaseSinkTestWithoutTelemetry):
    """Test xpath injection detection."""

    vulnerability_type = "XPATH_INJECTION"
    http_method = "POST"
    insecure_endpoint = "/iast/xpathi/test_insecure"
    secure_endpoint = "/iast/xpathi/test_secure"
    data = {"expression": "expression"}
    location_map = {"java": "com.datadoghq.system_tests.iast.utils.XPathExamples"}
