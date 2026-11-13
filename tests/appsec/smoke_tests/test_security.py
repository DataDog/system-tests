"""Security carrier preservation with native tracing."""

from utils import features, scenarios
from tests.appsec.smoke_tests.utils import BaseThreatsSmokeTests


@features.security_events_metadata
@scenarios.security_smoke
class Test_SecuritySmoke_Threats(BaseThreatsSmokeTests):
    pass
