"""AAP smoke coverage with classic Agent infrastructure and native tracing."""

from utils._context.constants import ContainerPorts
from utils._context.containers import VCRCassettesContainer

from ._core import DdTraceEndToEndScenario, FakeDatadogKey, scenario_groups


class SecuritySmoke(DdTraceEndToEndScenario):
    """AppSec payload carrier preservation through classic Agent infrastructure."""

    def __init__(self) -> None:
        super().__init__(
            "SECURITY_SMOKE",
            rc_api_enabled=True,
            other_weblog_containers=(VCRCassettesContainer,),
            weblog_env={
                "DD_AI_GUARD_ENABLED": "true",
                "DD_AI_GUARD_ENDPOINT": f"http://vcr_cassettes:{ContainerPorts.vcr_cassettes}/vcr/aiguard",
                "DD_API_KEY": FakeDatadogKey.AI_GUARD_API,
                "DD_APP_KEY": FakeDatadogKey.AI_GUARD_APP,
                "DD_TELEMETRY_METRICS_ENABLED": "true",
                "DD_TELEMETRY_METRICS_INTERVAL_SECONDS": "2.0",
                "DD_API_SECURITY_REQUEST_SAMPLE_RATE": "1.0",
                "DD_API_SECURITY_SAMPLE_DELAY": "0.0",
            },
            scenario_groups=[scenario_groups.appsec],
        )
