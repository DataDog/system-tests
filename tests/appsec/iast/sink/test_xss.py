# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features
from ..utils import BaseSinkTestWithoutTelemetry


@features.iast_sink_xss
class TestXSS(BaseSinkTestWithoutTelemetry):
    """Test xss detection."""

    vulnerability_type = "XSS"
    http_method = "POST"
    insecure_endpoint = "/iast/xss/test_insecure"
    secure_endpoint = "/iast/xss/test_secure"
    data = {"param": "param"}
    location_map = {"java": "com.datadoghq.system_tests.iast.utils.XSSExamples"}
