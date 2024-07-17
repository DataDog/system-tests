# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, missing_feature, features
from ..utils import BaseSinkTest


@features.iast_sink_code_injection
class TestCodeInjection(BaseSinkTest):
    """Test command injection detection."""

    vulnerability_type = "CODE_INJECTION"
    http_method = "POST"
    insecure_endpoint = "/iast/code_injection/test_insecure"
    secure_endpoint = "/iast/code_injection/test_secure"
    data = {"code": "1+2"}
    location_map = {
        "nodejs": {"express4": "iast/index.js", "express4-typescript": "iast.ts"},
    }
