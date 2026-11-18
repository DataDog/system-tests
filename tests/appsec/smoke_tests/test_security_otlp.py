"""Run the native AAP smoke contracts with OTLP traces converted by bundled DDOT."""

from utils import features, interfaces, pytest, scenarios
from tests.appsec.smoke_tests.utils import (
    BaseApiSecuritySmokeTests,
    BaseRaspSmokeTests,
    BaseRemoteConfigSmokeTests,
    BaseTelemetrySmokeTests,
    BaseThreatsSmokeTests,
    BaseUserEventsSmokeTests,
)


@pytest.fixture(autouse=True)
def _require_otlp_export(request: pytest.FixtureRequest) -> None:
    # Each shared setup method records a weblog response. Check its actual trace
    # transport so that SDKs silently falling back to native cannot pass.
    assert any(interfaces.open_telemetry.get_otel_trace_id(request.instance.r)), (
        "The request must be traced via OTLP through DDOT, not native trace export"
    )


@features.security_events_metadata
@features.support_in_app_waf_metrics_report
@scenarios.security_smoke_otlp
class Test_SecuritySmokeOtlp_Threats(BaseThreatsSmokeTests):
    pass


@features.rasp_local_file_inclusion
@features.rasp_server_side_request_forgery
@features.rasp_sql_injection
@features.rasp_shell_injection
@features.rasp_stack_trace
@features.rasp_span_tags
@scenarios.security_smoke_otlp
class Test_SecuritySmokeOtlp_Rasp(BaseRaspSmokeTests):
    pass


@features.waf_telemetry
@scenarios.security_smoke_otlp
class Test_SecuritySmokeOtlp_Telemetry(BaseTelemetrySmokeTests):
    pass


@features.threats_configuration
@features.appsec_request_blocking
@scenarios.security_smoke_otlp
class Test_SecuritySmokeOtlp_RemoteConfig(BaseRemoteConfigSmokeTests):
    pass


@features.api_security_schemas
@scenarios.security_smoke_otlp
class Test_SecuritySmokeOtlp_ApiSecurity(BaseApiSecuritySmokeTests):
    pass


@features.user_monitoring
@scenarios.security_smoke_otlp
class Test_SecuritySmokeOtlp_UserEvents(BaseUserEventsSmokeTests):
    pass
