from utils import weblog, interfaces, scenarios, features

from tests.test_config_consistency import *
from tests.test_standard_tags import *
from tests.test_scrubbing import *
from tests.test_semantic_conventions import *


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


CLASSES = [
    (Test_UrlQuery, []),
    (Test_EnvVar, []),
    (Test_Config_UnifiedServiceTagging_CustomService, []),
    (Test_StandardTagsMethod, []),
    (Test_StandardTagsUrl, []),
    (Test_StandardTagsUserAgent, []),
    (Test_StandardTagsClientIp, []),
    (
        Test_Meta,
        ["test_meta_component_tag"],
    ),  # The meta component tag would always be http.request and not external-processing
    (Test_MetricsStandardTags, []),
]

for cls, methods in CLASSES:

    @features.not_reported
    @scenarios.external_processing
    class Test_ExternalProcessing_APM_(cls):
        pytestmark = []

    for method in methods:
        setattr(Test_ExternalProcessing_APM_, method, lambda self: None)
        getattr(Test_ExternalProcessing_APM_, method).__test__ = False

    globals()[f"Test_ExternalProcessing_APM_{cls.__name__}"] = Test_ExternalProcessing_APM_

if len(CLASSES) > 0:
    del Test_ExternalProcessing_APM_
