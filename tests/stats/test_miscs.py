from utils import interfaces, bug, features, scenarios


@features.client_side_stats_supported
@scenarios.trace_stats_computation
class Test_Miscs:
    @bug(library="golang", reason="APMAPI-919")
    def test_request_headers(self):
        interfaces.library.assert_request_header(
            "/v0.6/stats", r"content-type", r"application/msgpack(, application/msgpack)?"
        )

    @scenarios.default
    def test_disable(self):
        requests = list(interfaces.library.get_data("/v0.6/stats"))
        assert len(requests) == 0, "Stats should be disabled by default"
