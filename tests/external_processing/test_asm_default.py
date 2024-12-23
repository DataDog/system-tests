from utils import scenarios, features, irrelevant, missing_feature
from tests.appsec import test_ip_blocking_full_denylist as base_ip_blocking_full_denylist
from tests.appsec import test_alpha as base_alpha
from tests.appsec import test_reports as base_reports
from tests.appsec import test_traces as base_traces
from tests.appsec import test_versions as base_versions


# Will not work: Automated login events, user ids, events tracking, usage of AppSec SDK
# Not tested due to lack of endpoints in the dummy http app: Block user, Block GraphQL, Fingerprinting
# Not tested because the test need appsec to be disabled at first (and in the scenario it's DD_APPSEC_ENABLED=1 at the start): Suspicious Attacker Blocking


@features.not_reported
@scenarios.external_processing
class Test_ExternalProcessing_ASM_AppSecIPBlockingFullDenylist(
    base_ip_blocking_full_denylist.Test_AppSecIPBlockingFullDenylist
):
    pass


@features.not_reported
@scenarios.external_processing
class Test_ExternalProcessing_ASM_Alpha_Basic(base_alpha.Test_Basic):
    pass


@features.not_reported
@scenarios.external_processing
class Test_ExternalProcessing_ASM_Events(base_versions.Test_Events):
    pass


@features.not_reported
@scenarios.external_processing
class Test_ExternalProcessing_ASM_RequestHeaders(base_reports.Test_RequestHeaders):
    pass


@features.not_reported
@scenarios.external_processing
class Test_ExternalProcessing_ASM_TagsFromRule(base_reports.Test_TagsFromRule):
    pass


@features.not_reported
@scenarios.external_processing
class Test_ExternalProcessing_ASM_ExtraTagsFromRule(base_reports.Test_ExtraTagsFromRule):
    pass


@features.not_reported
@scenarios.external_processing
class Test_ExternalProcessing_ASM_AttackTimestamp(base_reports.Test_AttackTimestamp):
    pass


@features.not_reported
@scenarios.external_processing
class Test_ExternalProcessing_ASM_RetainTraces(base_traces.Test_RetainTraces):
    pass


@features.not_reported
@scenarios.external_processing
class Test_ExternalProcessing_ASM_AppSecEventSpanTags(base_traces.Test_AppSecEventSpanTags):
    @irrelevant(True, reason="Irrelevant tag set for golang")
    def test_header_collection(self):
        pass


@features.not_reported
@scenarios.external_processing
class Test_ExternalProcessing_ASM_AppSecObfuscator(base_traces.Test_AppSecObfuscator):
    pass


@features.not_reported
@scenarios.external_processing
class Test_ExternalProcessing_ASM_CollectRespondHeaders(base_traces.Test_CollectRespondHeaders):
    @missing_feature(True, reason="The endpoint /headers is not implemented in the weblog")
    def test_header_collection(self):
        pass


@features.not_reported
@scenarios.external_processing
class Test_ExternalProcessing_ASM_CollectDefaultRequestHeader(base_traces.Test_CollectDefaultRequestHeader):
    pass


@features.not_reported
@scenarios.external_processing
class Test_ExternalProcessing_ASM_ExternalWafRequestsIdentification(base_traces.Test_ExternalWafRequestsIdentification):
    pass
