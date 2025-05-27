from utils._decorators import irrelevant
from utils.parametric.spec.trace import find_only_span
from utils import features, scenarios, context, missing_feature

import pytest

parametrize = pytest.mark.parametrize


def disable_baggage() -> pytest.MarkDecorator:
    env = {
        "DD_TRACE_PROPAGATION_STYLE": "datadog,tracecontext",
    }
    return parametrize("library_env", [env])


def only_baggage_enabled() -> pytest.MarkDecorator:
    env = {
        "DD_TRACE_PROPAGATION_STYLE": "baggage",
    }
    return parametrize("library_env", [env])


def specify_span_tags() -> pytest.MarkDecorator:
    env = {
        "DD_TRACE_BAGGAGE_TAG_KEYS": "session.id,foo",
    }
    return parametrize("library_env", [env])


def specify_span_tags_with_asterisk() -> pytest.MarkDecorator:
    env = {
        "DD_TRACE_BAGGAGE_TAG_KEYS": "account.id,feature*flag=xyz",
    }
    return parametrize("library_env", [env])


def all_span_tags() -> pytest.MarkDecorator:
    env = {
        "DD_TRACE_BAGGAGE_TAG_KEYS": "*",
    }
    return parametrize("library_env", [env])


def disable_span_tags() -> pytest.MarkDecorator:
    env = {
        "DD_TRACE_BAGGAGE_TAG_KEYS": "",
    }
    return parametrize("library_env", [env])


@features.datadog_headers_propagation
@scenarios.parametric
class Test_Headers_Baggage:
    def test_headers_baggage_default_D001(self, test_agent, test_library):
        """Ensure baggage is enabled as a default setting and that it does not interfere with Datadog headers."""
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [["x-datadog-trace-id", "123456789"], ["x-datadog-parent-id", "987654321"], ["baggage", "foo=bar"]]
            )

        span = find_only_span(test_agent.wait_for_num_traces(1))
        assert span.get("trace_id") == 123456789
        assert span.get("parent_id") == 987654321
        assert "baggage" in headers
        assert headers["baggage"] == "foo=bar"

    @only_baggage_enabled()
    @missing_feature(context.library == "nodejs", reason="pausing on this feature to avoid app crashes")
    def test_headers_baggage_only_D002(self, test_library):
        """Ensure that only baggage headers are injected when baggage is the only enabled propagation style."""
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [["x-datadog-trace-id", "123456789"], ["baggage", "foo=bar"]]
            )

        assert "x-datadog-trace-id" not in headers
        assert "x-datadog-parent-id" not in headers
        assert "baggage" in headers
        assert headers["baggage"] == "foo=bar"

    @irrelevant(
        context.library in ("cpp", "goland", "java", "ruby", "php"),
        reason="The current default behaviour matches the future baggage disabled behaviour, so we can't activate this test without causing a false easy win",
    )
    @disable_baggage()
    def test_baggage_disable_settings_D003(self, test_agent, test_library):
        """Ensure that baggage headers are not injected when baggage is disabled and does not interfere with other headers."""
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [["x-datadog-trace-id", "123456789"], ["x-datadog-parent-id", "987654321"], ["baggage", "foo=bar"]]
            )

        span = find_only_span(test_agent.wait_for_num_traces(1))
        assert span.get("trace_id") == 123456789
        assert span.get("parent_id") == 987654321
        assert "baggage" not in headers

    def test_baggage_inject_header_D004(self, test_library):
        """Testing baggage header injection, proper concatenation of key value pairs, and encoding"""
        with test_library.dd_start_span(name="test_baggage_set_D004") as span:
            span.set_baggage("foo", "bar")
            span.set_baggage("baz", "qux")
            span.set_baggage("userId", "Amélie")
            span.set_baggage("serverNode", "DF 28")
            span.set_baggage('",;\\()/:<=>?@[]{}', '",;\\')

            headers = test_library.dd_inject_headers(span.span_id)

        assert any("baggage" in header for header in headers)
        baggage_list: list = next((header for header in headers if header[0] == "baggage"), [])
        baggage_items = baggage_list[1].split(",")  # baggage items may not be in order
        assert len(baggage_items) == 5
        assert "foo=bar" in baggage_items
        assert "baz=qux" in baggage_items
        assert "userId=Am%C3%A9lie" in baggage_items
        assert "serverNode=DF%2028" in baggage_items
        assert "%22%2C%3B%5C%28%29%2F%3A%3C%3D%3E%3F%40%5B%5D%7B%7D=%22%2C%3B%5C" in baggage_items

    @missing_feature(
        context.library == "nodejs", reason="`dd_extract_headers_and_make_child_span` does not work with only baggage"
    )
    def test_baggage_extract_header_D005(self, test_library):
        """Testing baggage header extraction and decoding"""

        with test_library.dd_extract_headers_and_make_child_span(
            "test_baggage_extract_header_D005",
            [
                [
                    "baggage",
                    "foo=bar,userId=Am%C3%A9lie,serverNode=DF%2028,%22%2C%3B%5C%28%29%2F%3A%3C%3D%3E%3F%40%5B%5D%7B%7D=%22%2C%3B%5C",
                ]
            ],
        ) as span:
            assert span.get_baggage("foo") == "bar"
            assert span.get_baggage("userId") == "Amélie"
            assert span.get_baggage("serverNode") == "DF 28"
            assert span.get_baggage('",;\\()/:<=>?@[]{}') == '",;\\'
            assert span.get_all_baggage() == {
                "foo": "bar",
                "userId": "Amélie",
                "serverNode": "DF 28",
                '",;\\()/:<=>?@[]{}': '",;\\',
            }

    def test_baggage_set_D006(self, test_library):
        with test_library.dd_start_span(name="test_baggage_set_D006") as span:
            span.set_baggage("foo", "bar")
            span.set_baggage("baz", "qux")
            span.set_baggage("userId", "Amélie")
            span.set_baggage("serverNode", "DF 28")

            assert span.get_baggage("foo") == "bar"
            assert span.get_baggage("baz") == "qux"
            assert span.get_baggage("userId") == "Amélie"
            assert span.get_baggage("serverNode") == "DF 28"

    @irrelevant(
        context.library in ("cpp", "goland", "java", "ruby", "php"),
        reason="The current default behaviour matches the future baggage disabled behaviour, so we can't activate this test without causing a false easy win",
    )
    @disable_baggage()
    def test_baggage_set_disabled_D007(self, test_library):
        """Ensure that baggage headers are not injected when baggage is disabled."""
        with test_library.dd_start_span(name="test_baggage_set_disabled_D007") as span:
            span.set_baggage("foo", "bar")
            span.set_baggage("baz", "qux")

            headers = test_library.dd_inject_headers(span.span_id)
        assert not any("baggage" in item for item in headers)

    @missing_feature(
        context.library == "nodejs", reason="`dd_extract_headers_and_make_child_span` does not work with only baggage"
    )
    def test_baggage_get_D008(self, test_library):
        """Testing baggage API get_baggage"""
        with test_library.dd_extract_headers_and_make_child_span(
            "test_baggage_get_D008", [["baggage", "userId=Am%C3%A9lie,serverNode=DF%2028"]]
        ) as span:
            span.set_baggage("foo", "bar")
            span.set_baggage("baz", "qux")
            assert span.get_baggage("foo") == "bar"
            assert span.get_baggage("baz") == "qux"
            assert span.get_baggage("userId") == "Amélie"
            assert span.get_baggage("serverNode") == "DF 28"

    @missing_feature(
        context.library == "nodejs", reason="`dd_extract_headers_and_make_child_span` does not work with only baggage"
    )
    def test_baggage_get_all_D009(self, test_library):
        """Testing baggage API get_all_baggage"""
        with test_library.dd_extract_headers_and_make_child_span(
            "test_baggage_get_all_D009", [["baggage", "foo=bar"]]
        ) as span:
            span.set_baggage("baz", "qux")
            span.set_baggage("userId", "Amélie")
            span.set_baggage("serverNode", "DF 28")
            baggage = span.get_all_baggage()
            assert baggage == {"foo": "bar", "baz": "qux", "userId": "Amélie", "serverNode": "DF 28"}

    def test_baggage_remove_D010(self, test_library):
        """Testing baggage API remove_baggage"""
        with test_library.dd_start_span(name="test_baggage_remove_D010") as span:
            span.set_baggage("baz", "qux")
            span.set_baggage("userId", "Amélie")
            span.set_baggage("serverNode", "DF 28")
            span.remove_baggage("baz")
            span.remove_baggage("userId")
            assert span.get_all_baggage() == {"serverNode": "DF 28"}
            span.remove_baggage("serverNode")
            assert span.get_all_baggage() == {}

    def test_baggage_remove_all_D011(self, test_library):
        """Testing baggage API remove_all_baggage"""
        with test_library.dd_start_span(name="test_baggage_remove_all_D011") as span:
            span.set_baggage("foo", "bar")
            span.set_baggage("baz", "qux")
            span.remove_all_baggage()
            assert span.get_all_baggage() == {}

    def _assert_valid_baggage(self, test_library):
        """Helper function to confirm that a valid baggage header is set
        when calling dd_make_child_span_and_get_headers.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers([["baggage", "foo=valid"]])
            assert "baggage" in headers

    @missing_feature(
        context.library == "nodejs",
        reason="`dd_make_child_span_and_get_headers` calls `dd_extract_headers_and_make_child_span`, which does not work with only baggage",
    )
    def test_baggage_malformed_headers_D012(self, test_library):
        """Ensure that malformed baggage headers are handled properly. Unable to use get_baggage functions because it does not return anything"""
        Test_Headers_Baggage._assert_valid_baggage(self, test_library)

        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [["baggage", "no-equal-sign,foo=gets-dropped-because-previous-pair-is-malformed"]],
            )

            assert "baggage" not in headers

    @missing_feature(
        context.library == "nodejs",
        reason="`dd_make_child_span_and_get_headers` calls `dd_extract_headers_and_make_child_span`, which does not work with only baggage",
    )
    def test_baggage_malformed_headers_D013(self, test_library):
        """Ensure that malformed baggage headers are handled properly. Unable to use get_baggage functions because it does not return anything"""
        Test_Headers_Baggage._assert_valid_baggage(self, test_library)

        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers([["baggage", "=no-key"]])

            assert "baggage" not in headers

    @missing_feature(
        context.library == "nodejs",
        reason="`dd_make_child_span_and_get_headers` calls `dd_extract_headers_and_make_child_span`, which does not work with only baggage",
    )
    def test_baggage_malformed_headers_D014(self, test_library):
        Test_Headers_Baggage._assert_valid_baggage(self, test_library)

        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers([["baggage", "no-value="]])

            assert "baggage" not in headers

    @missing_feature(
        context.library == "nodejs",
        reason="`dd_make_child_span_and_get_headers` calls `dd_extract_headers_and_make_child_span`, which does not work with only baggage",
    )
    def test_baggage_malformed_headers_D015(self, test_library):
        Test_Headers_Baggage._assert_valid_baggage(self, test_library)

        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [["baggage", "foo=gets-dropped-because-subsequent-pair-is-malformed,="]],
            )

            assert "baggage" not in headers

    def test_baggageheader_maxitems_inject_D016(self, test_library):
        """Ensure that baggage headers are not injected when the number of baggage items exceeds the maximum number of items."""
        max_items = 64
        with test_library.dd_start_span(name="test_baggageheader_maxitems_inject_D016") as span:
            for i in range(max_items + 2):
                span.set_baggage(f"key{i}", f"value{i}")

            headers = test_library.dd_inject_headers(span.span_id)
            for header in headers:
                if "baggage" in header:
                    baggage_header = header
            items = baggage_header[1].split(",")
            assert len(items) == max_items

    def test_baggageheader_maxbytes_inject_D017(self, test_library):
        """Ensure that baggage headers are not injected when the total byte size of the baggage exceeds the maximum size."""
        max_bytes = 8192
        with test_library.dd_start_span(name="test_baggageheader_maxbytes_inject_D017") as span:
            baggage_items = {
                "key1": "a" * (max_bytes // 3),
                "key2": "b" * (max_bytes // 3),
                "key3": "c" * (max_bytes // 3),
                "key4": "d",
            }
            for key, value in baggage_items.items():
                span.set_baggage(key, value)

            headers = test_library.dd_inject_headers(span.span_id)
            for header in headers:
                if "baggage" in header:
                    baggage_header = header
            items = baggage_header[1].split(",")
            header_size = len(baggage_header[1].encode("utf-8"))
            assert len(items) == 2
            assert header_size <= max_bytes


@features.baggage_span_tags
@scenarios.parametric
class Test_Headers_Baggage_Span_Tags:
    def test_baggage_span_tags_default(self, test_agent, test_library):
        """Ensure baggage is enabled as a default setting and that it does not interfere with Datadog headers."""
        with test_library:
            _ = test_library.dd_make_child_span_and_get_headers(
                [
                    ["x-datadog-trace-id", "123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["baggage", "user.id=doggo,session.id=mysession,foo=bar"],
                ]
            )

        span = find_only_span(test_agent.wait_for_num_traces(1))
        meta = span.get("meta")
        assert meta is not None
        assert meta.get("baggage.user.id") == "doggo"
        assert meta.get("baggage.session.id") == "mysession"
        assert meta.get("baggage.foo") is None

    @specify_span_tags()
    def test_baggage_span_tags_specific_keys(self, test_agent, test_library):
        """Ensure baggage is enabled as a default setting and that it does not interfere with Datadog headers."""
        with test_library:
            _ = test_library.dd_make_child_span_and_get_headers(
                [
                    ["x-datadog-trace-id", "123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["baggage", "user.id=doggo,session.id=fakesession,account.id=123,foo=bar"],
                ]
            )

        span = find_only_span(test_agent.wait_for_num_traces(1))
        meta = span.get("meta")
        assert meta is not None
        assert meta.get("baggage.user.id") is None
        assert meta.get("baggage.session.id") == "fakesession"
        assert meta.get("baggage.foo") == "bar"
        assert meta.get("baggage.account.id") is None

    @all_span_tags()
    def test_baggage_span_tags_all(self, test_agent, test_library):
        """Ensure baggage is enabled as a default setting and that it does not interfere with Datadog headers."""
        with test_library:
            _ = test_library.dd_make_child_span_and_get_headers(
                [
                    ["x-datadog-trace-id", "123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["baggage", "user.id=bits,session.id=mysession,account.id=9871,serverNode=DF 28,region=us-east-1"],
                ]
            )

        span = find_only_span(test_agent.wait_for_num_traces(1))
        meta = span.get("meta")
        assert meta is not None
        assert meta.get("baggage.user.id") == "bits"
        assert meta.get("baggage.session.id") == "mysession"
        assert meta.get("baggage.account.id") == "9871"
        assert meta.get("baggage.serverNode") == "DF 28"
        assert meta.get("baggage.region") == "us-east-1"

    def test_baggage_span_tags_malformed_header(self, test_agent, test_library):
        """Ensure baggage is enabled as a default setting and that it does not interfere with Datadog headers."""
        with test_library:
            _ = test_library.dd_make_child_span_and_get_headers(
                [
                    ["x-datadog-trace-id", "123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["baggage", "user.id=,session.id=mysession,account.id=abcd"],
                ]
            )

        span = find_only_span(test_agent.wait_for_num_traces(1))
        meta = span.get("meta")
        assert meta is not None
        # if a header is malformed, all items get dropped
        # therefore, there are no baggage tags
        assert meta.get("baggage.user.id") is None
        assert meta.get("baggage.session.id") is None
        assert meta.get("baggage.account.id") is None

    @disable_span_tags()
    def test_baggage_span_tags_disabled(self, test_agent, test_library):
        """Ensure baggage is enabled as a default setting and that it does not interfere with Datadog headers."""
        with test_library:
            _ = test_library.dd_make_child_span_and_get_headers(
                [
                    ["x-datadog-trace-id", "123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["baggage", "user.id=alice,session.id=xyz123,locale=en-US,account.id=12345"],
                ]
            )

        span = find_only_span(test_agent.wait_for_num_traces(1))
        meta = span.get("meta")
        assert meta is not None
        assert meta.get("baggage.user.id") is None
        assert meta.get("baggage.session.id") is None
        assert meta.get("baggage.account.id") is None
        assert meta.get("baggage.locale") is None

    @specify_span_tags_with_asterisk()
    def test_baggage_span_tags_key_with_asterisk(self, test_agent, test_library):
        """Ensure baggage is enabled as a default setting and that it does not interfere with Datadog headers."""
        with test_library:
            _ = test_library.dd_make_child_span_and_get_headers(
                [
                    ["x-datadog-trace-id", "123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["baggage", "user.id=doggo,account.id=testaccount,foo=bar,feature*flag=xyz"],
                ]
            )

        span = find_only_span(test_agent.wait_for_num_traces(1))
        meta = span.get("meta")
        assert meta is not None
        assert meta.get("baggage.user.id") is None
        assert meta.get("baggage.account.id") == "testaccount"
        assert meta.get("baggage.foo") is None
        assert meta.get("baggage.feature*flag") == "xyz"
