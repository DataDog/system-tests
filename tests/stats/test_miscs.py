from utils import interfaces, bug, features


@features.client_side_stats_supported
class Test_Miscs:
    @bug(library="golang", reason="content-type is not provided")
    def test_request_headers(self):
        interfaces.library.assert_request_header(
            "/v0.6/stats", r"content-type", r"application/msgpack(, application/msgpack)?"
        )
