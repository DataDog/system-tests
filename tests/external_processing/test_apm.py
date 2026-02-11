from utils import weblog, interfaces, features, scenarios


@scenarios.go_proxies_default
@features.go_proxies
class Test_GoProxies_Tracing:
    def setup_correct_span_structure(self):
        self.r = weblog.get("/")

    def test_correct_span_structure(self):
        assert self.r.status_code == 200
        interfaces.library.assert_trace_exists(self.r)
        span, span_format = interfaces.library.get_root_span(self.r)
        assert span["type"] == "web"
        meta = interfaces.library.get_span_meta(span, span_format)
        assert meta["span.kind"] == "server"
        assert meta["http.url"] == "http://localhost:7777/"
        assert meta["http.host"] == "localhost:7777"
