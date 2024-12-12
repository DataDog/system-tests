from utils import scenarios, features
from utils import remote_config as rc

from tests.appsec.test_alpha import *
from tests.appsec.test_blocking_addresses import *
from tests.appsec.test_ip_blocking_full_denylist import *
from tests.appsec.test_logs import *
from tests.appsec.test_reports import *
from tests.appsec.test_request_blocking import *
from tests.appsec.test_runtime_activation import *
from tests.appsec.test_suspicious_attacker_blocking import *
from tests.appsec.test_traces import *
from tests.appsec.test_versions import *

# Will not work: Automated login events, user ids, events tracking, usage of AppSec SDK
# Not tested due to lack of endpoints in the dummy http app: Block user, Block GraphQL, Fingerprinting
# Not tested because the test need appsec to be disabled at first (and in the scenario it's DD_APPSEC_ENABLED=1 at the start): Suspicious Attacker Blocking

CLASSES = [
    (Test_AppSecIPBlockingFullDenylist, []),
    (Test_Basic, []),
    (Test_Events, []),
    (Test_Blocking_client_ip, []),
    (Test_Blocking_request_method, ["test_blocking_before"]),  # endpoint /tag_value is not implemented
    (Test_Blocking_request_uri, ["test_blocking_before"]),  # endpoint /tag_value is not implemented
    (
        Test_Blocking_request_path_params,
        ["test_blocking", "test_blocking_before"],
    ),  # endpoint /param is not implemented
    (Test_Blocking_request_query, ["test_blocking_before"]),  # endpoint /tag_value is not implemented
    (Test_Blocking_request_headers, ["test_blocking_before"]),  # endpoint /tag_value is not implemented
    (Test_Blocking_request_cookies, ["test_blocking_before"]),  # endpoint /tag_value is not implemented
    (
        Test_Blocking_response_status,
        ["test_blocking", "test_non_blocking", "test_not_found"],
    ),  # endpoint /finger_print (404) and /tag_value are not implemented
    (Test_Blocking_response_headers, ["test_blocking", "test_non_blocking"]),  # endpoint /tag_value is not implemented
    (Test_RequestHeaders, []),
    (Test_TagsFromRule, []),
    (Test_ExtraTagsFromRule, []),
    (Test_AttackTimestamp, []),
    (Test_AppSecRequestBlocking, []),
    (Test_RetainTraces, []),
    (Test_AppSecEventSpanTags, ["test_header_collection"]),  # irrelevant tag set for golang
    (Test_AppSecObfuscator, []),
    (Test_CollectRespondHeaders, ["test_header_collection"]),  # endpoint /headers is not implemented
    (Test_CollectDefaultRequestHeader, []),
    (Test_ExternalWafRequestsIdentification, []),
]

# Rule files:
blocking_rule = ("datadog/2/ASM_DD/rules/config", json.load(open("tests/appsec/blocking_rule.json")))

for cls, methods in CLASSES:

    @features.not_reported
    @scenarios.external_processing
    class Test_ExternalProcessing_ASM_(cls):
        pytestmark = []

        def _setup_rulefile(self, orig, rulefile):
            rc.rc_state.set_config(*rulefile).apply()
            orig()
            rc.rc_state.reset().apply()

        def setup_blocking(self):
            self._setup_rulefile(super().setup_blocking, blocking_rule)

        def setup_blocking_before(self):
            self._setup_rulefile(super().setup_blocking_before, blocking_rule)

        def setup_blocking_uri_raw(self):
            self._setup_rulefile(super().setup_blocking_uri_raw, blocking_rule)

    for method in methods:
        setattr(Test_ExternalProcessing_ASM_, method, lambda self: None)
        getattr(Test_ExternalProcessing_ASM_, method).__test__ = False

    globals()[f"Test_ExternalProcessing_ASM_{cls.__name__}"] = Test_ExternalProcessing_ASM_

if len(CLASSES) > 0:
    del Test_ExternalProcessing_ASM_
