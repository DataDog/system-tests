from utils import weblog, interfaces, scenarios, features


@features.haproxy_stream_processing_offload
@scenarios.stream_processing_offload
class Test_StreamProcessingOffload_Tracing:
    def setup_correct_span_structure(self):
        self.r = weblog.get("/")

    def test_correct_span_structure(self):
        assert self.r.status_code == 200
        interfaces.library.assert_trace_exists(self.r)
        span = interfaces.library.get_root_span(self.r)
        assert span["type"] == "web"
        assert span["meta"]["span.kind"] == "server"
        assert span["meta"]["http.url"] == "http://localhost:7777/"
        assert span["meta"]["http.host"] == "localhost:7777"
