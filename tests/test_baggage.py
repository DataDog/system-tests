import json
import pytest
from urllib import request
from utils import weblog, interfaces, scenarios, features, context
from utils.tools import logger


@scenarios.datadog_baggage_propagation
@features.datadog_baggage_headers
class Test_Baggage_Headers_Basic:
    def setup_main(self):
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={"x-datadog-parent-id": "10", "x-datadog-trace-id": "2", "baggage": "foo=bar"},
        )

    def test_main(self):
        interfaces.library.assert_trace_exists(self.r)

        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        assert "baggage" in data["request_headers"]


@scenarios.datadog_baggage_propagation
@features.datadog_baggage_headers
class Test_Baggage_Headers_Malformed:
    def setup_main(self):
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={
                "x-datadog-parent-id": "10",
                "x-datadog-trace-id": "2",
                "baggage": "no-equal-sign,foo=gets-dropped-because-previous-pair-is-malformed",
            },
        )

    def test_main(self):
        interfaces.library.assert_trace_exists(self.r)

        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        assert "baggage" not in data["request_headers"]

    # def test_case1(self):
    #     # "Malformed" case #1
    #     self.r = weblog.get(
    #         "/make_distant_call",
    #         params={"url": "http://weblog:7777"},
    #         headers={"x-datadog-parent-id": "10", "x-datadog-trace-id": "2", "baggage": "no-equal-sign,foo=gets-dropped-because-previous-pair-is-malformed"}
    #     )
    #     self._assert_baggage_is_absent()

    # def test_case2(self):
    #     # "Malformed" case #2
    #     self.r = weblog.get(
    #         "/make_distant_call",
    #         params={"url": "http://weblog:7777"},
    #         headers={"x-datadog-parent-id": "10", "x-datadog-trace-id": "2", "baggage": "=no-key"}
    #     )
    #     self._assert_baggage_is_absent()

    # def _assert_baggage_is_absent(self):
    #     # This is effectively your "test_main" assertion code
    #     interfaces.library.assert_trace_exists(self.r)
    #     assert self.r.status_code == 200

    #     data = json.loads(self.r.text)
    #     assert "baggage" not in data["request_headers"]
