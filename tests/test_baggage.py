import json
import pytest
from urllib import request
from utils import weblog, interfaces, scenarios, features, context
from utils.tools import logger


@scenarios.default
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
        for header in data["request_headers"]:
            if header.get("key") == "baggage":
                baggage_value = header.get("value")
                break

        assert baggage_value is not None
        assert "foo=bar" in baggage_value

@scenarios.default
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
        assert any(d["key"] != "baggage" for d in data["request_headers"])


@scenarios.default
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
        assert any(d["key"] != "baggage" for d in data["request_headers"])


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
        for header in data["request_headers"]:
            if header.get("key") == "baggage":
                baggage_value = header.get("value")
                break

        assert baggage_value is not None
        assert "foo=bar" in baggage_value

@scenarios.default
@features.datadog_baggage_headers
class Test_Baggage_Headers_Max_Items:
    def setup_main(self):
        self.max_items = 64
        baggage_items = [f"key{i}=value{i}" for i in range(self.max_items + 2)]
        baggage_header = ",".join(baggage_items)
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={
                "x-datadog-parent-id": "10",
                "x-datadog-trace-id": "2",
                "baggage": baggage_header,
            },
        )

    def test_main(self):
        interfaces.library.assert_trace_exists(self.r)

        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        baggage_header_value = None
        for header in data["request_headers"]:
            if header.get("key") == "baggage":
                baggage_header_value = header.get("value")
                break

        assert baggage_header_value is not None
        items = baggage_header_value[0].split(",")
        assert len(items) == self.max_items


@scenarios.default
@features.datadog_baggage_headers
class Test_Baggage_Headers_Max_Bytes:
    def setup_main(self):
        self.max_bytes = 8192
        baggage_items = {
            "key1": "a" * (self.max_bytes // 3),
            "key2": "b" * (self.max_bytes // 3),
            "key3": "c" * (self.max_bytes // 3),
            "key4": "d",
        }

        full_baggage_header = ",".join([f"{k}={v}" for k, v in baggage_items.items()])
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={
                "x-datadog-parent-id": "10",
                "x-datadog-trace-id": "2",
                "baggage": full_baggage_header,
            },
        )

    def test_main(self):
        interfaces.library.assert_trace_exists(self.r)
        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        baggage_header_value = None
        for header in data["request_headers"]:
            if header.get("key") == "baggage":
                baggage_header_value = header.get("value")
                break
        assert baggage_header_value is not None
        header_str = baggage_header_value[0]

        items = header_str.split(",")
        assert len(items) == 2

        header_size = len(header_str.encode("utf-8"))
        assert header_size <= self.max_bytes