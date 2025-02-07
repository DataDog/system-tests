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
        assert data["request_headers"]["baggage"] == "foo=bar"


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
        # note to self: want to avoid doing negative assertions.. is there a way to avoid this?
        assert "baggage" not in data["request_headers"]


@scenarios.datadog_baggage_propagation
@features.datadog_baggage_headers
class Test_Baggage_Headers_Malformed2:
    def setup_main(self):
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={"x-datadog-parent-id": "10", "x-datadog-trace-id": "2", "baggage": "=no-key"},
        )

    def test_main(self):
        interfaces.library.assert_trace_exists(self.r)

        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        # note to self: want to avoid doing negative assertions.. is there a way to avoid this?
        assert "baggage" not in data["request_headers"]


@scenarios.only_baggage_propagation
@features.datadog_baggage_headers
class Test_Only_Baggage_Header:
    def setup_main(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777"}, headers={"baggage": "foo=bar"})

    # currently only works for tracers where baggage is separate from spans
    # but it should work for all tracers that support baggage
    def test_main(self):
        interfaces.library.assert_trace_exists(self.r)

        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        assert any(d["key"] == "baggage" for d in data["request_headers"])
