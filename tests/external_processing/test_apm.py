from tests import test_scrubbing as base_scrubbing
from tests import test_config_consistency as base_config_consistency
from tests import test_standard_tags as base_standard_tags
from tests import test_semantic_conventions as base_semantic_conventions
from utils import weblog, interfaces, scenarios, features


@features.not_reported  # it's just a POC. We'll need to figure out how we want to see results in FPD
@scenarios.external_processing
class Test_ExternalProcessing_Tracing:
    def setup_correct_span_structure(self):
        self.r = weblog.get("/")

    def test_correct_span_structure(self):
        assert self.r.status_code == 200

        interfaces.library.assert_trace_exists(self.r)
        for _, span in interfaces.library.get_root_spans(request=self.r):
            assert span["type"] == "web"
            assert span["meta"]["span.kind"] == "server"
            assert span["meta"]["http.url"] == "http://localhost:7777/"
            assert span["meta"]["http.host"] == "localhost:7777"


@features.not_reported
@scenarios.external_processing
class Test_ExternalProcessing_APM_UrlQuery(base_scrubbing.Test_UrlQuery):
    pass


@features.not_reported
@scenarios.external_processing
class Test_ExternalProcessing_APM_EnvVar(base_scrubbing.Test_EnvVar):
    pass


@features.not_reported
@scenarios.external_processing
class Test_ExternalProcessing_APM_Config_UnifiedServiceTagging_CustomService(
    base_config_consistency.Test_Config_UnifiedServiceTagging_CustomService
):
    pass


@features.not_reported
@scenarios.external_processing
class Test_ExternalProcessing_APM_StandardTagsMethod(base_standard_tags.Test_StandardTagsMethod):
    pass


@features.not_reported
@scenarios.external_processing
class Test_ExternalProcessing_APM_StandardTagsUrl(base_standard_tags.Test_StandardTagsUrl):
    pass


@features.not_reported
@scenarios.external_processing
class Test_ExternalProcessing_APM_StandardTagsUserAgent(base_standard_tags.Test_StandardTagsUserAgent):
    pass


@features.not_reported
@scenarios.external_processing
class Test_ExternalProcessing_APM_StandardTagsClientIp(base_standard_tags.Test_StandardTagsClientIp):
    pass


@features.not_reported
@scenarios.external_processing
class Test_ExternalProcessing_APM_Meta(base_semantic_conventions.Test_Meta):
    def test_meta_component_tag(self):
        pass


@features.not_reported
@scenarios.external_processing
class Test_ExternalProcessing_APM_MetricsStandardTags(base_semantic_conventions.Test_MetricsStandardTags):
    pass
