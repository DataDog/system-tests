"""AAP smoke tests with classic Agent infrastructure and native tracing."""

from utils import features, scenarios
from tests.appsec.smoke_tests.utils import (
    BaseApiSecuritySmokeTests,
    BaseIastSmokeTests,
    BaseRaspSmokeTests,
    BaseRemoteConfigSmokeTests,
    BaseTelemetrySmokeTests,
    BaseThreatsSmokeTests,
    BaseUserEventsSmokeTests,
)


@features.security_events_metadata
@features.support_in_app_waf_metrics_report
@scenarios.security_smoke
class Test_SecuritySmoke_Threats(BaseThreatsSmokeTests):
    pass


@features.rasp_local_file_inclusion
@features.rasp_server_side_request_forgery
@features.rasp_sql_injection
@features.rasp_shell_injection
@features.rasp_stack_trace
@features.rasp_span_tags
@scenarios.security_smoke
class Test_SecuritySmoke_Rasp(BaseRaspSmokeTests):
    pass


@features.waf_telemetry
@scenarios.security_smoke
class Test_SecuritySmoke_Telemetry(BaseTelemetrySmokeTests):
    pass


@features.threats_configuration
@features.appsec_request_blocking
@scenarios.security_smoke
class Test_SecuritySmoke_RemoteConfig(BaseRemoteConfigSmokeTests):
    pass


@features.api_security_schemas
@scenarios.security_smoke
class Test_SecuritySmoke_ApiSecurity(BaseApiSecuritySmokeTests):
    pass


@features.user_monitoring
@scenarios.security_smoke
class Test_SecuritySmoke_UserEvents(BaseUserEventsSmokeTests):
    pass


@features.iast_sink_path_traversal
@features.iast_stack_trace
@scenarios.security_smoke
class Test_SecuritySmoke_Iast(BaseIastSmokeTests):
    pass
