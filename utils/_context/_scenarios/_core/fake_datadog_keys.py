from enum import StrEnum


class FakeDatadogKey(StrEnum):
    """Fake API and app keys scenarios give to the tested components, when no real Datadog backend is involved.

    Tests must not use them directly: they get them from the running scenario (e.g. scenario.dd_api_key).
    """

    DEFAULT = "0123456789abcdef0123456789abcdef"
    """API key of the agent, and of the weblog when it sends to the mocked backend"""

    SIDECAR = "fedcba9876543210fedcba9876543210"
    """API key of serverless-init: it tells, in the mocked backend, what it relayed from what the weblog sent"""

    AI_GUARD_API = "mock_api_key"
    """API key of AI Guard weblogs, ignored by the VCR cassettes"""

    AI_GUARD_APP = "mock_app_key"
    """App key of AI Guard weblogs, ignored by the VCR cassettes"""

    OTEL_COLLECTOR = "0123"
    """API key of the OpenTelemetry collector, sending to the mocked backend"""

    PARAMETRIC = "system-tests-mock-api-key"
    """API key of the parametric libraries"""
