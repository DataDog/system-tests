from utils import weblog, interfaces, scenarios, features


@features.envoy_external_processing
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
