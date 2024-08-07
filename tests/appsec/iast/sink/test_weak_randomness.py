# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, flaky, context
from ..utils import BaseSinkTestWithoutTelemetry


@features.iast_sink_weakrandomness
@flaky(context.library >= "dotnet@2.54.0", reason="APPSEC-54151")
class TestWeakRandomness(BaseSinkTestWithoutTelemetry):
    """Test weak randomness detection."""

    vulnerability_type = "WEAK_RANDOMNESS"
    http_method = "GET"
    insecure_endpoint = "/iast/weak_randomness/test_insecure"
    secure_endpoint = "/iast/weak_randomness/test_secure"
    data = None
    location_map = {
        "java": "com.datadoghq.system_tests.iast.utils.WeakRandomnessExamples",
        "python": {"flask-poc": "app.py", "django-poc": "app/urls.py"},
        "nodejs": {"express4": "iast/index.js", "express4-typescript": "iast.ts"},
    }
