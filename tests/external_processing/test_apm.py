from utils import weblog, interfaces, features, context, irrelevant


@irrelevant(context.weblog_variant not in ("haproxy", "envoy"))
@features.go_proxies
class Test_GoProxies_Tracing:
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
