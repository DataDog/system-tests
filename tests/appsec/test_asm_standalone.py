import json
import re

from utils import weblog, interfaces, scenarios, features, rfc
from utils._context.header_tag_vars import *
from requests.structures import CaseInsensitiveDict

# Python regexp that matches:
# "GET /requestdownstream"
# "GET /requestdownstream/"
# "GET requestdownstream"
# "GET requestdownstream/"
REQUESTDOWNSTREAM_RESOURCE_PATTERN = re.compile(r'GET /?requestdownstream/?')

@rfc("https://docs.google.com/document/d/12NBx-nD-IoQEMiCRnJXneq4Be7cbtSc6pJLOFUWTpNE/edit")
@features.appsec_standalone
@scenarios.appsec_standalone
class Test_AppSecStandalone_UpstreamPropagation:
    """APM correctly propagates AppSec events in distributing tracing."""

    # TODO downstream propagation

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
        for data, _, span in interfaces.library.get_spans(request=self.r):
            if not REQUESTDOWNSTREAM_RESOURCE_PATTERN.search(span["resource"]):
                continue

            assert span["metrics"]["_sampling_priority_v1"] < 2
            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert "_dd.p.appsec" not in span["meta"]
            assert "_dd.p.other" in span["meta"]
            assert span["trace_id"] == 1212121212121212121

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
            "/requestdownstream/",
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
        for data, _, span in interfaces.library.get_spans(request=self.r):
            if not REQUESTDOWNSTREAM_RESOURCE_PATTERN.search(span["resource"]):
                continue

            assert span["metrics"]["_sampling_priority_v1"] < 2
            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert "_dd.p.appsec" not in span["meta"]
            assert "_dd.p.other" in span["meta"]
            assert span["trace_id"] == 1212121212121212121

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
            "/requestdownstream/",
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
        for data, _, span in interfaces.library.get_spans(request=self.r):
            if not REQUESTDOWNSTREAM_RESOURCE_PATTERN.search(span["resource"]):
                continue

            assert span["metrics"]["_sampling_priority_v1"] < 2
            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert "_dd.p.appsec" not in span["meta"]
            assert "_dd.p.other" in span["meta"]
            assert span["trace_id"] == 1212121212121212121

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
            "/requestdownstream/",
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
        for data, _, span in interfaces.library.get_spans(request=self.r):
            if not REQUESTDOWNSTREAM_RESOURCE_PATTERN.search(span["resource"]):
                continue

            assert span["metrics"]["_sampling_priority_v1"] < 2
            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert "_dd.p.appsec" not in span["meta"]
            assert "_dd.p.other" in span["meta"]
            assert span["trace_id"] == 1212121212121212121

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

    def test_no_upstream_appsec_propagation__with_attack__is_kept_with_priority_2__from_minus_1(self):
        spans_checked = 0
        for data, _, span in interfaces.library.get_spans(request=self.r):
            if not REQUESTDOWNSTREAM_RESOURCE_PATTERN.search(span["resource"]):
                continue

            assert span["metrics"]["_sampling_priority_v1"] == 2
            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert span["meta"]["_dd.p.appsec"] == "1"
            assert span["trace_id"] == 1212121212121212121

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
            "/requestdownstream/",
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
                "x-datadog-origin": "rum",
                "x-datadog-sampling-priority": "0",
                "x-datadog-tags": "_dd.p.other=1",
                "User-Agent": "Arachni/v1",
            },
        )

    def test_no_upstream_appsec_propagation__with_attack__is_kept_with_priority_2__from_0(self):
        spans_checked = 0
        for data, _, span in interfaces.library.get_spans(request=self.r):
            if not REQUESTDOWNSTREAM_RESOURCE_PATTERN.search(span["resource"]):
                continue

            assert span["metrics"]["_sampling_priority_v1"] == 2
            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert span["meta"]["_dd.p.appsec"] == "1"
            assert span["trace_id"] == 1212121212121212121

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
            "/requestdownstream/",
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
        for data, _, span in interfaces.library.get_spans(request=self.r):
            if not REQUESTDOWNSTREAM_RESOURCE_PATTERN.search(span["resource"]):
                continue

            assert span["metrics"]["_sampling_priority_v1"] == 2
            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert span["meta"]["_dd.p.appsec"] == "1"
            assert span["trace_id"] == 1212121212121212121

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

    def setup_upstream_appsec_propagation__no_attack__is_propagated_as_is__being_1(self):
        trace_id = 1212121212121212121
        parent_id = 34343434
        self.r = weblog.get(
            "/requestdownstream/",
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
        for data, _, span in interfaces.library.get_spans(request=self.r):
            if not REQUESTDOWNSTREAM_RESOURCE_PATTERN.search(span["resource"]):
                continue

            assert span["metrics"]["_sampling_priority_v1"] == 2
            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert span["meta"]["_dd.p.appsec"] == "1"
            assert span["trace_id"] == 1212121212121212121

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
        for data, _, span in interfaces.library.get_spans(request=self.r):
            if not REQUESTDOWNSTREAM_RESOURCE_PATTERN.search(span["resource"]):
                continue

            assert span["metrics"]["_sampling_priority_v1"] == 2
            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert span["meta"]["_dd.p.appsec"] == "1"
            assert span["trace_id"] == 1212121212121212121

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

    def test_any_upstream_propagation__with_attack__raises_priority_to_2__from_minus_1(self):
        spans_checked = 0
        for data, _, span in interfaces.library.get_spans(request=self.r):
            if not REQUESTDOWNSTREAM_RESOURCE_PATTERN.search(span["resource"]):
                continue

            assert span["metrics"]["_sampling_priority_v1"] == 2
            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert span["meta"]["_dd.p.appsec"] == "1"
            assert span["trace_id"] == 1212121212121212121

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
            "/requestdownstream/",
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
                "x-datadog-origin": "rum",
                "x-datadog-sampling-priority": "0",
                "User-Agent": "Arachni/v1",
            },
        )

    def test_any_upstream_propagation__with_attack__raises_priority_to_2__from_0(self):
        spans_checked = 0
        for data, _, span in interfaces.library.get_spans(request=self.r):
            if not REQUESTDOWNSTREAM_RESOURCE_PATTERN.search(span["resource"]):
                continue

            assert span["metrics"]["_sampling_priority_v1"] == 2
            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert span["meta"]["_dd.p.appsec"] == "1"
            assert span["trace_id"] == 1212121212121212121

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
            "/requestdownstream/",
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
                "x-datadog-origin": "rum",
                "x-datadog-sampling-priority": "1",
                "User-Agent": "Arachni/v1",
            },
        )

    def test_any_upstream_propagation__with_attack__raises_priority_to_2__from_1(self):
        spans_checked = 0
        for data, _, span in interfaces.library.get_spans(request=self.r):
            if not REQUESTDOWNSTREAM_RESOURCE_PATTERN.search(span["resource"]):
                continue

            assert span["metrics"]["_sampling_priority_v1"] == 2
            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert span["meta"]["_dd.p.appsec"] == "1"
            assert span["trace_id"] == 1212121212121212121

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
