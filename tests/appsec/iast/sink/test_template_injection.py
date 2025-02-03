# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features
from ..utils import BaseSinkTest


@features.iast_sink_template_injection
class TestTemplateInjection(BaseSinkTest):
    """Test template injection detection."""

    vulnerability_type = "TEMPLATE_INJECTION"
    http_method = "POST"
    insecure_endpoint = "/iast/template_injection/test_insecure"
    secure_endpoint = "/iast/template_injection/test_secure"

    data = {"template": "Hello"}
