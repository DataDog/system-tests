# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features
from ..utils import BaseSinkTest


@features.iast_sink_untrusted_deserialization
class TestUntrustedDeserialization(BaseSinkTest):
    """Test untrusted deserialization detection."""

    vulnerability_type = "UNTRUSTED_DESERIALIZATION"
    http_method = "GET"
    insecure_endpoint = "/iast/untrusted_deserialization/test_insecure"
    secure_endpoint = "/iast/untrusted_deserialization/test_secure"
    location_map = {"java": "com.datadoghq.system_tests.iast.utils.DeserializationExamples"}