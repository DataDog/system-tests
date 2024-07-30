import json
import re

from utils import weblog, interfaces, scenarios, features, rfc, bug, context
from utils._context.header_tag_vars import *
from requests.structures import CaseInsensitiveDict

# Python regexp that matches:
# "GET /requestdownstream"
# "GET /requestdownstream/"
# "GET requestdownstream"
# "GET requestdownstream/"
REQUESTDOWNSTREAM_RESOURCE_PATTERN = re.compile(r"GET /?requestdownstream/?")


@rfc("https://docs.google.com/document/d/12NBx-nD-IoQEMiCRnJXneq4Be7cbtSc6pJLOFUWTpNE/edit")
@features.appsec_standalone
@scenarios.appsec_standalone
@bug(context.library > "python@2.9.2", reason="Missing Jira ticket")
class Test_AppSecStandalone_UpstreamPropagation:
    """APM correctly propagates AppSec events in distributing tracing."""

    # TODO downstream propagation

    # This methods exist to test the 2 different ways of setting the tags in the tracers.
    # In some tracers, the propagation tags are set in the first span of every trace chunk,
    # while in others they are set in the local root span. (same for the sampling priority tag)
    # This method test the first case and if it fails, it will test the second case. When both cases fail, the test will fail.
    #
    # first_trace is the first span of every trace chunk
    # span is the local root span
    # obj is the object where the tags are set (meta, metrics)
    # expected_tags is a dict of tag name to value
    #   - The key is the tag name
    #   - The value can be None to assert that the tag is not present
    #   - The value can be a string to assert the value of the tag
    #   - The value can be a lambda function that will be used to assert the value of the tag (special case for _sampling_priority_v1)
    #
    # Return a boolean indicating if the test passed
    @staticmethod
    def _assert_tags(first_trace, span, obj, expected_tags):
        def _assert_tags_value(span, obj, expected_tags):
            struct = span if obj is None else span[obj]
            for tag, value in expected_tags.items():
                if value is None:
                    assert tag not in struct
                else:
                    if tag == "_sampling_priority_v1":  # special case, it's a lambda to check for a condition
                        assert value(struct[tag])
                    else:
                        assert struct[tag] == value

        # Case 1: The tags are set on the first span of every trace chunk
        try:
            _assert_tags_value(first_trace, obj, expected_tags)
            return True
        except (KeyError, AssertionError) as e:
            pass  # should try the second case

        # Case 2: The tags are set on the local root span
        try:
            _assert_tags_value(span, obj, expected_tags)
            return True
        except (KeyError, AssertionError) as e:
            return False

    def setup_no_appsec_upstream__no_attack__is_kept_with_priority_1__from_minus_1(self):
        trace_id = 1212121212121212121
        parent_id = 34343434
        self.r = weblog.get(
            "/requestdownstream",
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
                "x-datadog-sampling-priority": "-1",
                "x-datadog-origin": "rum",
                "x-datadog-tags": "_dd.p.other=1",
            },
        )

    def test_no_appsec_upstream__no_attack__is_kept_with_priority_1__from_minus_1(self):
        spans_checked = 0
        tested_meta = {"_dd.p.appsec": None, "_dd.p.other": "1"}
        tested_metrics = {"_sampling_priority_v1": lambda x: x < 2}

        for data, trace, span in interfaces.library.get_spans(request=self.r):
            if not REQUESTDOWNSTREAM_RESOURCE_PATTERN.search(span["resource"]):
                continue

            assert self._assert_tags(trace[0], span, "meta", tested_meta)
            assert self._assert_tags(trace[0], span, "metrics", tested_metrics)

            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert span["trace_id"] == 1212121212121212121
            assert trace[0]["trace_id"] == 1212121212121212121

            # Some tracers use true while others use yes
            assert any(
                ["Datadog-Client-Computed-Stats", trueish,] in data["request"]["headers"] for trueish in ["yes", "true"]
            )
            spans_checked += 1

        assert spans_checked == 1
        # Downstream propagation is fully disabled in this case
        downstream_headers = CaseInsensitiveDict(json.loads(self.r.text))
        assert "X-Datadog-Origin" not in downstream_headers
        assert "X-Datadog-Parent-Id" not in downstream_headers
        assert "X-Datadog-Tags" not in downstream_headers
        assert "X-Datadog-Sampling-Priority" not in downstream_headers
        assert "X-Datadog-Trace-Id" not in downstream_headers

    def setup_no_appsec_upstream__no_attack__is_kept_with_priority_1__from_0(self):
        trace_id = 1212121212121212121
        parent_id = 34343434
        self.r = weblog.get(
            "/requestdownstream",
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
                "x-datadog-sampling-priority": "0",
                "x-datadog-origin": "rum",
                "x-datadog-tags": "_dd.p.other=1",
            },
        )

    def test_no_appsec_upstream__no_attack__is_kept_with_priority_1__from_0(self):
        spans_checked = 0
        tested_meta = {"_dd.p.appsec": None, "_dd.p.other": "1"}
        tested_metrics = {"_sampling_priority_v1": lambda x: x < 2}

        for data, trace, span in interfaces.library.get_spans(request=self.r):
            if not REQUESTDOWNSTREAM_RESOURCE_PATTERN.search(span["resource"]):
                continue

            assert self._assert_tags(trace[0], span, "meta", tested_meta)
            assert self._assert_tags(trace[0], span, "metrics", tested_metrics)

            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert span["trace_id"] == 1212121212121212121
            assert trace[0]["trace_id"] == 1212121212121212121

            # Some tracers use true while others use yes
            assert any(
                ["Datadog-Client-Computed-Stats", trueish,] in data["request"]["headers"] for trueish in ["yes", "true"]
            )
            spans_checked += 1

        assert spans_checked == 1
        # Downstream propagation is fully disabled in this case
        downstream_headers = CaseInsensitiveDict(json.loads(self.r.text))
        assert "X-Datadog-Origin" not in downstream_headers
        assert "X-Datadog-Parent-Id" not in downstream_headers
        assert "X-Datadog-Tags" not in downstream_headers
        assert "X-Datadog-Sampling-Priority" not in downstream_headers
        assert "X-Datadog-Trace-Id" not in downstream_headers

    def setup_no_appsec_upstream__no_attack__is_kept_with_priority_1__from_1(self):
        trace_id = 1212121212121212121
        parent_id = 34343434
        self.r = weblog.get(
            "/requestdownstream",
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
                "x-datadog-sampling-priority": "1",
                "x-datadog-origin": "rum",
                "x-datadog-tags": "_dd.p.other=1",
            },
        )

    def test_no_appsec_upstream__no_attack__is_kept_with_priority_1__from_1(self):
        spans_checked = 0
        tested_meta = {"_dd.p.appsec": None, "_dd.p.other": "1"}
        tested_metrics = {"_sampling_priority_v1": lambda x: x < 2}

        for data, trace, span in interfaces.library.get_spans(request=self.r):
            if not REQUESTDOWNSTREAM_RESOURCE_PATTERN.search(span["resource"]):
                continue

            assert self._assert_tags(trace[0], span, "meta", tested_meta)
            assert self._assert_tags(trace[0], span, "metrics", tested_metrics)

            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert span["trace_id"] == 1212121212121212121
            assert trace[0]["trace_id"] == 1212121212121212121

            # Some tracers use true while others use yes
            assert any(
                ["Datadog-Client-Computed-Stats", trueish,] in data["request"]["headers"] for trueish in ["yes", "true"]
            )
            spans_checked += 1

        assert spans_checked == 1
        # Downstream propagation is fully disabled in this case
        downstream_headers = CaseInsensitiveDict(json.loads(self.r.text))
        assert "X-Datadog-Origin" not in downstream_headers
        assert "X-Datadog-Parent-Id" not in downstream_headers
        assert "X-Datadog-Tags" not in downstream_headers
        assert "X-Datadog-Sampling-Priority" not in downstream_headers
        assert "X-Datadog-Trace-Id" not in downstream_headers

    def setup_no_appsec_upstream__no_attack__is_kept_with_priority_1__from_2(self):
        trace_id = 1212121212121212121
        parent_id = 34343434
        self.r = weblog.get(
            "/requestdownstream",
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
                "x-datadog-sampling-priority": "2",
                "x-datadog-origin": "rum",
                "x-datadog-tags": "_dd.p.other=1",
            },
        )

    def test_no_appsec_upstream__no_attack__is_kept_with_priority_1__from_2(self):
        spans_checked = 0
        tested_meta = {"_dd.p.appsec": None, "_dd.p.other": "1"}
        tested_metrics = {"_sampling_priority_v1": lambda x: x < 2}

        for data, trace, span in interfaces.library.get_spans(request=self.r):
            if not REQUESTDOWNSTREAM_RESOURCE_PATTERN.search(span["resource"]):
                continue

            assert self._assert_tags(trace[0], span, "meta", tested_meta)
            assert self._assert_tags(trace[0], span, "metrics", tested_metrics)

            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert span["trace_id"] == 1212121212121212121
            assert trace[0]["trace_id"] == 1212121212121212121

            # Some tracers use true while others use yes
            assert any(
                ["Datadog-Client-Computed-Stats", trueish,] in data["request"]["headers"] for trueish in ["yes", "true"]
            )
            spans_checked += 1

        assert spans_checked == 1
        # Downstream propagation is fully disabled in this case
        downstream_headers = CaseInsensitiveDict(json.loads(self.r.text))
        assert "X-Datadog-Origin" not in downstream_headers
        assert "X-Datadog-Parent-Id" not in downstream_headers
        assert "X-Datadog-Tags" not in downstream_headers
        assert "X-Datadog-Sampling-Priority" not in downstream_headers
        assert "X-Datadog-Trace-Id" not in downstream_headers

    def setup_no_upstream_appsec_propagation__with_attack__is_kept_with_priority_2__from_minus_1(self):
        trace_id = 1212121212121212121
        parent_id = 34343434
        self.r = weblog.get(
            "/requestdownstream",
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
                "x-datadog-origin": "rum",
                "x-datadog-sampling-priority": "-1",
                "x-datadog-tags": "_dd.p.other=1",
                "User-Agent": "Arachni/v1",
            },
        )

    @bug(
        library="java",
        weblog_variant="akka-http",
        reason="KeyError x-datadog-origin - span not available on appsec events drives into no propagation tags",
    )
    @bug(
        library="java",
        weblog_variant="jersey-grizzly2",
        reason="KeyError x-datadog-origin - span not available on appsec events drives into no propagation tags",
    )
    @bug(
        library="java",
        weblog_variant="play",
        reason="KeyError x-datadog-origin - span not available on appsec events drives into no propagation tags",
    )
    def test_no_upstream_appsec_propagation__with_attack__is_kept_with_priority_2__from_minus_1(self):
        spans_checked = 0
        tested_meta = {"_dd.p.appsec": "1"}
        tested_metrics = {"_sampling_priority_v1": lambda x: x == 2}

        for data, trace, span in interfaces.library.get_spans(request=self.r):
            if not REQUESTDOWNSTREAM_RESOURCE_PATTERN.search(span["resource"]):
                continue

            assert self._assert_tags(trace[0], span, "meta", tested_meta)
            assert self._assert_tags(trace[0], span, "metrics", tested_metrics)

            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert span["trace_id"] == 1212121212121212121
            assert trace[0]["trace_id"] == 1212121212121212121

            # Some tracers use true while others use yes
            assert any(
                ["Datadog-Client-Computed-Stats", trueish,] in data["request"]["headers"] for trueish in ["yes", "true"]
            )
            spans_checked += 1

        assert spans_checked == 1
        downstream_headers = CaseInsensitiveDict(json.loads(self.r.text))
        assert downstream_headers["X-Datadog-Origin"] == "rum"
        assert downstream_headers["X-Datadog-Parent-Id"] != "34343434"
        assert "_dd.p.other=1" in downstream_headers["X-Datadog-Tags"]
        assert "_dd.p.appsec=1" in downstream_headers["X-Datadog-Tags"]
        assert downstream_headers["X-Datadog-Sampling-Priority"] == "2"
        assert downstream_headers["X-Datadog-Trace-Id"] == "1212121212121212121"

    def setup_no_upstream_appsec_propagation__with_attack__is_kept_with_priority_2__from_0(self):
        trace_id = 1212121212121212121
        parent_id = 34343434
        self.r = weblog.get(
            "/requestdownstream",
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
                "x-datadog-origin": "rum",
                "x-datadog-sampling-priority": "0",
                "x-datadog-tags": "_dd.p.other=1",
                "User-Agent": "Arachni/v1",
            },
        )

    @bug(
        library="java",
        weblog_variant="akka-http",
        reason="KeyError x-datadog-origin - span not available on appsec events drives into no propagation tags",
    )
    @bug(
        library="java",
        weblog_variant="jersey-grizzly2",
        reason="KeyError x-datadog-origin - span not available on appsec events drives into no propagation tags",
    )
    @bug(
        library="java",
        weblog_variant="play",
        reason="KeyError x-datadog-origin - span not available on appsec events drives into no propagation tags",
    )
    def test_no_upstream_appsec_propagation__with_attack__is_kept_with_priority_2__from_0(self):
        spans_checked = 0
        tested_meta = {"_dd.p.appsec": "1"}
        tested_metrics = {"_sampling_priority_v1": lambda x: x == 2}

        for data, trace, span in interfaces.library.get_spans(request=self.r):
            if not REQUESTDOWNSTREAM_RESOURCE_PATTERN.search(span["resource"]):
                continue

            assert self._assert_tags(trace[0], span, "meta", tested_meta)
            assert self._assert_tags(trace[0], span, "metrics", tested_metrics)

            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert span["trace_id"] == 1212121212121212121
            assert trace[0]["trace_id"] == 1212121212121212121

            # Some tracers use true while others use yes
            assert any(
                ["Datadog-Client-Computed-Stats", trueish,] in data["request"]["headers"] for trueish in ["yes", "true"]
            )
            spans_checked += 1

        assert spans_checked == 1
        downstream_headers = CaseInsensitiveDict(json.loads(self.r.text))
        assert downstream_headers["X-Datadog-Origin"] == "rum"
        assert downstream_headers["X-Datadog-Parent-Id"] != "34343434"
        assert "_dd.p.other=1" in downstream_headers["X-Datadog-Tags"]
        assert "_dd.p.appsec=1" in downstream_headers["X-Datadog-Tags"]
        assert downstream_headers["X-Datadog-Sampling-Priority"] == "2"
        assert downstream_headers["X-Datadog-Trace-Id"] == "1212121212121212121"

    def setup_upstream_appsec_propagation__no_attack__is_propagated_as_is__being_0(self):
        trace_id = 1212121212121212121
        parent_id = 34343434
        self.r = weblog.get(
            "/requestdownstream",
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
                "x-datadog-origin": "rum",
                "x-datadog-sampling-priority": "0",
                "x-datadog-tags": "_dd.p.appsec=1",
            },
        )

    def test_upstream_appsec_propagation__no_attack__is_propagated_as_is__being_0(self):
        spans_checked = 0
        tested_meta = {"_dd.p.appsec": "1"}
        tested_metrics = {"_sampling_priority_v1": lambda x: x in [0, 2]}

        for data, trace, span in interfaces.library.get_spans(request=self.r):
            if not REQUESTDOWNSTREAM_RESOURCE_PATTERN.search(span["resource"]):
                continue

            assert self._assert_tags(trace[0], span, "meta", tested_meta)
            assert self._assert_tags(trace[0], span, "metrics", tested_metrics)

            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert span["trace_id"] == 1212121212121212121
            assert trace[0]["trace_id"] == 1212121212121212121

            # Some tracers use true while others use yes
            assert any(
                ["Datadog-Client-Computed-Stats", trueish,] in data["request"]["headers"] for trueish in ["yes", "true"]
            )
            spans_checked += 1

        assert spans_checked == 1
        downstream_headers = CaseInsensitiveDict(json.loads(self.r.text))
        assert downstream_headers["X-Datadog-Origin"] == "rum"
        assert downstream_headers["X-Datadog-Parent-Id"] != "34343434"
        assert "_dd.p.appsec=1" in downstream_headers["X-Datadog-Tags"]
        assert downstream_headers["X-Datadog-Sampling-Priority"] in ["0", "2"]
        assert downstream_headers["X-Datadog-Trace-Id"] == "1212121212121212121"

    def setup_upstream_appsec_propagation__no_attack__is_propagated_as_is__being_1(self):
        trace_id = 1212121212121212121
        parent_id = 34343434
        self.r = weblog.get(
            "/requestdownstream",
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
                "x-datadog-origin": "rum",
                "x-datadog-sampling-priority": "1",
                "x-datadog-tags": "_dd.p.appsec=1",
            },
        )

    def test_upstream_appsec_propagation__no_attack__is_propagated_as_is__being_1(self):
        spans_checked = 0
        tested_meta = {"_dd.p.appsec": "1"}
        tested_metrics = {"_sampling_priority_v1": lambda x: x in [1, 2]}

        for data, trace, span in interfaces.library.get_spans(request=self.r):
            if not REQUESTDOWNSTREAM_RESOURCE_PATTERN.search(span["resource"]):
                continue

            assert self._assert_tags(trace[0], span, "meta", tested_meta)
            assert self._assert_tags(trace[0], span, "metrics", tested_metrics)

            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert span["trace_id"] == 1212121212121212121
            assert trace[0]["trace_id"] == 1212121212121212121

            # Some tracers use true while others use yes
            assert any(
                ["Datadog-Client-Computed-Stats", trueish,] in data["request"]["headers"] for trueish in ["yes", "true"]
            )
            spans_checked += 1

        assert spans_checked == 1
        downstream_headers = CaseInsensitiveDict(json.loads(self.r.text))
        assert downstream_headers["X-Datadog-Origin"] == "rum"
        assert downstream_headers["X-Datadog-Parent-Id"] != "34343434"
        assert "_dd.p.appsec=1" in downstream_headers["X-Datadog-Tags"]
        assert downstream_headers["X-Datadog-Sampling-Priority"] in ["1", "2"]
        assert downstream_headers["X-Datadog-Trace-Id"] == "1212121212121212121"

    def setup_upstream_appsec_propagation__no_attack__is_propagated_as_is__being_2(self):
        trace_id = 1212121212121212121
        parent_id = 34343434
        self.r = weblog.get(
            "/requestdownstream",
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
                "x-datadog-origin": "rum",
                "x-datadog-sampling-priority": "2",
                "x-datadog-tags": "_dd.p.appsec=1",
            },
        )

    def test_upstream_appsec_propagation__no_attack__is_propagated_as_is__being_2(self):
        spans_checked = 0
        tested_meta = {"_dd.p.appsec": "1"}
        tested_metrics = {"_sampling_priority_v1": lambda x: x == 2}

        for data, trace, span in interfaces.library.get_spans(request=self.r):
            if not REQUESTDOWNSTREAM_RESOURCE_PATTERN.search(span["resource"]):
                continue

            assert self._assert_tags(trace[0], span, "meta", tested_meta)
            assert self._assert_tags(trace[0], span, "metrics", tested_metrics)

            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert span["trace_id"] == 1212121212121212121
            assert trace[0]["trace_id"] == 1212121212121212121

            # Some tracers use true while others use yes
            assert any(
                ["Datadog-Client-Computed-Stats", trueish,] in data["request"]["headers"] for trueish in ["yes", "true"]
            )
            spans_checked += 1

        assert spans_checked == 1
        downstream_headers = CaseInsensitiveDict(json.loads(self.r.text))
        assert downstream_headers["X-Datadog-Origin"] == "rum"
        assert downstream_headers["X-Datadog-Parent-Id"] != "34343434"
        assert "_dd.p.appsec=1" in downstream_headers["X-Datadog-Tags"]
        assert downstream_headers["X-Datadog-Sampling-Priority"] == "2"
        assert downstream_headers["X-Datadog-Trace-Id"] == "1212121212121212121"

    def setup_any_upstream_propagation__with_attack__raises_priority_to_2__from_minus_1(self):
        trace_id = 1212121212121212121
        parent_id = 34343434
        self.r = weblog.get(
            "/requestdownstream",
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
                "x-datadog-origin": "rum",
                "x-datadog-sampling-priority": "-1",
                "User-Agent": "Arachni/v1",
            },
        )

    @bug(
        library="java",
        weblog_variant="akka-http",
        reason="KeyError x-datadog-origin - span not available on appsec events drives into no propagation tags",
    )
    @bug(
        library="java",
        weblog_variant="jersey-grizzly2",
        reason="KeyError x-datadog-origin - span not available on appsec events drives into no propagation tags",
    )
    @bug(
        library="java",
        weblog_variant="play",
        reason="KeyError x-datadog-origin - span not available on appsec events drives into no propagation tags",
    )
    def test_any_upstream_propagation__with_attack__raises_priority_to_2__from_minus_1(self):
        spans_checked = 0
        tested_meta = {"_dd.p.appsec": "1"}
        tested_metrics = {"_sampling_priority_v1": lambda x: x == 2}

        for data, trace, span in interfaces.library.get_spans(request=self.r):
            if not REQUESTDOWNSTREAM_RESOURCE_PATTERN.search(span["resource"]):
                continue

            assert self._assert_tags(trace[0], span, "meta", tested_meta)
            assert self._assert_tags(trace[0], span, "metrics", tested_metrics)

            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert span["trace_id"] == 1212121212121212121
            assert trace[0]["trace_id"] == 1212121212121212121

            # Some tracers use true while others use yes
            assert any(
                ["Datadog-Client-Computed-Stats", trueish,] in data["request"]["headers"] for trueish in ["yes", "true"]
            )
            spans_checked += 1

        assert spans_checked == 1
        downstream_headers = CaseInsensitiveDict(json.loads(self.r.text))
        assert downstream_headers["X-Datadog-Origin"] == "rum"
        assert downstream_headers["X-Datadog-Parent-Id"] != "34343434"
        assert "_dd.p.appsec=1" in downstream_headers["X-Datadog-Tags"]
        assert downstream_headers["X-Datadog-Sampling-Priority"] == "2"
        assert downstream_headers["X-Datadog-Trace-Id"] == "1212121212121212121"

    def setup_any_upstream_propagation__with_attack__raises_priority_to_2__from_0(self):
        trace_id = 1212121212121212121
        parent_id = 34343434
        self.r = weblog.get(
            "/requestdownstream",
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
                "x-datadog-origin": "rum",
                "x-datadog-sampling-priority": "0",
                "User-Agent": "Arachni/v1",
            },
        )

    @bug(
        library="java",
        weblog_variant="akka-http",
        reason="KeyError x-datadog-origin - span not available on appsec events drives into no propagation tags",
    )
    @bug(
        library="java",
        weblog_variant="jersey-grizzly2",
        reason="KeyError x-datadog-origin - span not available on appsec events drives into no propagation tags",
    )
    @bug(
        library="java",
        weblog_variant="play",
        reason="KeyError x-datadog-origin - span not available on appsec events drives into no propagation tags",
    )
    def test_any_upstream_propagation__with_attack__raises_priority_to_2__from_0(self):
        spans_checked = 0
        tested_meta = {"_dd.p.appsec": "1"}
        tested_metrics = {"_sampling_priority_v1": lambda x: x == 2}

        for data, trace, span in interfaces.library.get_spans(request=self.r):
            if not REQUESTDOWNSTREAM_RESOURCE_PATTERN.search(span["resource"]):
                continue

            assert self._assert_tags(trace[0], span, "meta", tested_meta)
            assert self._assert_tags(trace[0], span, "metrics", tested_metrics)

            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert span["trace_id"] == 1212121212121212121
            assert trace[0]["trace_id"] == 1212121212121212121

            # Some tracers use true while others use yes
            assert any(
                ["Datadog-Client-Computed-Stats", trueish,] in data["request"]["headers"] for trueish in ["yes", "true"]
            )
            spans_checked += 1

        assert spans_checked == 1
        downstream_headers = CaseInsensitiveDict(json.loads(self.r.text))
        assert downstream_headers["X-Datadog-Origin"] == "rum"
        assert downstream_headers["X-Datadog-Parent-Id"] != "34343434"
        assert "_dd.p.appsec=1" in downstream_headers["X-Datadog-Tags"]
        assert downstream_headers["X-Datadog-Sampling-Priority"] == "2"
        assert downstream_headers["X-Datadog-Trace-Id"] == "1212121212121212121"

    def setup_any_upstream_propagation__with_attack__raises_priority_to_2__from_1(self):
        trace_id = 1212121212121212121
        parent_id = 34343434
        self.r = weblog.get(
            "/requestdownstream",
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
                "x-datadog-origin": "rum",
                "x-datadog-sampling-priority": "1",
                "User-Agent": "Arachni/v1",
            },
        )

    @bug(
        library="java",
        weblog_variant="akka-http",
        reason="KeyError x-datadog-origin - span not available on appsec events drives into no propagation tags",
    )
    @bug(
        library="java",
        weblog_variant="jersey-grizzly2",
        reason="KeyError x-datadog-origin - span not available on appsec events drives into no propagation tags",
    )
    @bug(
        library="java",
        weblog_variant="play",
        reason="KeyError x-datadog-origin - span not available on appsec events drives into no propagation tags",
    )
    def test_any_upstream_propagation__with_attack__raises_priority_to_2__from_1(self):
        spans_checked = 0
        tested_meta = {"_dd.p.appsec": "1"}
        tested_metrics = {"_sampling_priority_v1": lambda x: x == 2}

        for data, trace, span in interfaces.library.get_spans(request=self.r):
            if not REQUESTDOWNSTREAM_RESOURCE_PATTERN.search(span["resource"]):
                continue

            assert self._assert_tags(trace[0], span, "meta", tested_meta)
            assert self._assert_tags(trace[0], span, "metrics", tested_metrics)

            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert span["trace_id"] == 1212121212121212121
            assert trace[0]["trace_id"] == 1212121212121212121

            # Some tracers use true while others use yes
            assert any(
                ["Datadog-Client-Computed-Stats", trueish,] in data["request"]["headers"] for trueish in ["yes", "true"]
            )
            spans_checked += 1

        assert spans_checked == 1
        downstream_headers = CaseInsensitiveDict(json.loads(self.r.text))
        assert downstream_headers["X-Datadog-Origin"] == "rum"
        assert downstream_headers["X-Datadog-Parent-Id"] != "34343434"
        assert "_dd.p.appsec=1" in downstream_headers["X-Datadog-Tags"]
        assert downstream_headers["X-Datadog-Sampling-Priority"] == "2"
        assert downstream_headers["X-Datadog-Trace-Id"] == "1212121212121212121"
