import json
import requests
from utils import weblog, interfaces, features, scenarios


def extract_baggage_value(request_headers: dict | list):
    """Helper function that returns the baggage header value from the given headers.
    Supports both a list of header objects and a dict.
    """
    if isinstance(request_headers, dict):
        # Case-insensitive lookup for baggage header since dependening on the weblog app implementation
        for key, value in request_headers.items():
            if key.lower() == "baggage":
                return value
    elif isinstance(request_headers, list):
        for header in request_headers:
            if header.get("key", "").lower() == "baggage":
                return header.get("value")
    return None


def _setup_baggage_api_request(endpoint: str):
    return weblog.get(
        endpoint,
        params={
            "url": "http://weblog:7777",
            "baggage_set": "foo=overwrite_value,new_foo=new_value",
            "baggage_remove": "remove_me_key",
        },
        headers={
            "x-datadog-parent-id": "10",
            "x-datadog-trace-id": "2",
            "baggage": "foo=value_to_be_replaced,FOO=UNTOUCHED,remove_me_key=remove_me_value",
        },
    )


def _assert_baggage_api_response(response: requests.Response):
    assert response.status_code == 200
    data = json.loads(response.text)
    baggage_header_value = extract_baggage_value(data["request_headers"])
    assert baggage_header_value is not None
    header_str = baggage_header_value[0] if isinstance(baggage_header_value, list) else baggage_header_value
    items = header_str.split(",")

    # Expect the following baggage items:
    # - "foo=overwrite_value (new pair with conflicting case-sensitive key replaces old pair)
    # - "FOO=BAR (keys are case-sensitive, so it does not get replaced)
    # - "new_foo=new_value (new pair added)
    assert len(items) == 3
    assert "foo=overwrite_value" in items
    assert "FOO=UNTOUCHED" in items
    assert "new_foo=new_value" in items


@scenarios.tracing_config_empty
@features.datadog_baggage_headers
class Test_Baggage_Headers_Basic:
    def setup_basic(self):
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={"x-datadog-parent-id": "10", "x-datadog-trace-id": "2", "baggage": "foo=bar"},
        )

    def test_basic(self):
        interfaces.library.assert_trace_exists(self.r)
        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        baggage_value = extract_baggage_value(data["request_headers"])
        assert baggage_value is not None
        assert "foo=bar" in baggage_value


@scenarios.tracing_config_empty
@features.datadog_baggage_headers
class Test_Baggage_Headers_Malformed:
    def setup_malformed(self):
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={
                "x-datadog-parent-id": "10",
                "x-datadog-trace-id": "2",
                "baggage": "no-equal-sign,foo=gets-dropped-because-previous-pair-is-malformed",
            },
        )

    def test_malformed(self):
        interfaces.library.assert_trace_exists(self.r)
        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        headers = data["request_headers"]
        # When headers is a dict, ensure "baggage" key is absent.
        if isinstance(headers, dict):
            assert "baggage" not in headers
        # When headers is a list, ensure no header entry has key "baggage"
        elif isinstance(headers, list):
            assert all(header.get("key") != "baggage" for header in headers)


@scenarios.tracing_config_empty
@features.datadog_baggage_headers
class Test_Baggage_Headers_Malformed2:
    def setup_malformed_2(self):
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={"x-datadog-parent-id": "10", "x-datadog-trace-id": "2", "baggage": "=no-key"},
        )

    def test_malformed_2(self):
        interfaces.library.assert_trace_exists(self.r)
        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        headers = data["request_headers"]
        if isinstance(headers, dict):
            assert "baggage" not in headers
        elif isinstance(headers, list):
            assert all(header.get("key") != "baggage" for header in headers)


@scenarios.tracing_config_empty
@features.datadog_baggage_headers
class Test_Only_Baggage_Header:
    def setup_only_baggage(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777"}, headers={"baggage": "foo=bar"})

    def test_only_baggage(self):
        interfaces.library.assert_trace_exists(self.r)
        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        baggage_value = extract_baggage_value(data["request_headers"])
        assert baggage_value is not None
        assert "foo=bar" in baggage_value


@scenarios.tracing_config_empty
@features.datadog_baggage_headers
class Test_Baggage_Headers_Max_Items:
    def setup_max_headers(self):
        self.max_items = 64
        baggage_items = [f"key{i}=value{i}" for i in range(self.max_items + 2)]
        baggage_header = ",".join(baggage_items)
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={
                "x-datadog-parent-id": "10",
                "x-datadog-trace-id": "2",
                "x-datadog-sampling-priority": "1",
                "baggage": baggage_header,
            },
        )

    def test_max_headers(self):
        interfaces.library.assert_trace_exists(self.r)
        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        baggage_header_value = extract_baggage_value(data["request_headers"])
        assert baggage_header_value is not None
        header_str = baggage_header_value[0] if isinstance(baggage_header_value, list) else baggage_header_value
        items = header_str.split(",")
        # Ensure we respect the max items limit
        assert len(items) == self.max_items


@scenarios.tracing_config_empty
@features.datadog_baggage_headers
class Test_Baggage_Headers_Max_Bytes:
    def setup_max_bytes(self):
        self.max_bytes = 8192
        baggage_items = {
            "key1": "a" * (self.max_bytes // 2),
            "key2": "b" * (self.max_bytes // 2),
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

    def test_max_bytes(self):
        interfaces.library.assert_trace_exists(self.r)
        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        baggage_header_value = extract_baggage_value(data["request_headers"])
        assert baggage_header_value is not None
        header_str = baggage_header_value[0] if isinstance(baggage_header_value, list) else baggage_header_value
        items = header_str.split(",")
        # Expect only one baggage item to be injected because the full header exceeds max_bytes
        assert len(items) == 1
        header_size = len(header_str.encode("utf-8"))
        assert header_size <= self.max_bytes


# Note: This currently relies on DD_TRACE_OTEL_ENABLED=true
@scenarios.tracing_config_nondefault_4
@features.datadog_baggage_headers
class Test_Baggage_Headers_Api_OTel:
    def setup_otel_api_update(self):
        self.r = _setup_baggage_api_request("/otel_drop_in_baggage_api_otel")

    def test_otel_api_update(self):
        interfaces.library.assert_trace_exists(self.r)
        _assert_baggage_api_response(self.r)


@scenarios.tracing_config_empty
@features.datadog_baggage_headers
class Test_Baggage_Headers_Api_Datadog:
    def setup_datadog_api_update(self):
        self.r = _setup_baggage_api_request("/otel_drop_in_baggage_api_datadog")

    def test_datadog_api_update(self):
        interfaces.library.assert_trace_exists(self.r)
        _assert_baggage_api_response(self.r)
