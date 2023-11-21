# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import coverage
from .._test_iast_fixtures import BaseSinkTestWithoutTelemetry


@coverage.basic
class TestXPathInjection(BaseSinkTestWithoutTelemetry):
    """Test xpath injection detection."""

    vulnerability_type = "XPATH_INJECTION"
    http_method = "POST"
    insecure_endpoint = "/iast/xpathi/test_insecure"
    secure_endpoint = "/iast/xpathi/test_secure"
    data = {"expression": "expression"}
    location_map = {"java": "com.datadoghq.system_tests.iast.utils.XPathExamples"}
