import json
from abc import ABC, abstractmethod
import time

from requests.structures import CaseInsensitiveDict

from utils.telemetry_utils import TelemetryUtils
from utils import context, weblog, interfaces, scenarios, features, rfc, bug, missing_feature, irrelevant, logger, flaky

USER = "test"
NEW_USER = "testnew"
INVALID_USER = "invalidUser"
UUID_USER = "testuuid"
PASSWORD = "1234"


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
def assert_tags(first_trace, span, obj, expected_tags) -> bool:
    def _assert_tags_value(span, obj, expected_tags):
        struct = span if obj is None else span[obj]
        for tag, value in expected_tags.items():
            if value is None:
                assert tag not in struct
            elif tag == "_sampling_priority_v1":  # special case, it's a lambda to check for a condition
                assert value(struct[tag])
            else:
                assert struct[tag] == value

    # Case 1: The tags are set on the first span of every trace chunk
    try:
        _assert_tags_value(first_trace, obj, expected_tags)
        return True
    except (KeyError, AssertionError):
        pass  # should try the second case

    # Case 2: The tags are set on the local root span
    try:
        _assert_tags_value(span, obj, expected_tags)
        return True
    except (KeyError, AssertionError):
        return False


class BaseAsmStandaloneUpstreamPropagation(ABC):
    """APM correctly propagates AppSec events in distributing tracing."""

    # TODO downstream propagation

    # Enpoint that triggers an ASM event and a downstream request
    request_downstream_url: str = "/requestdownstream"

    # Tested product
    tested_product: str | None = None

    @staticmethod
    def assert_product_is_enabled(response, product) -> None:
        assert response.status_code is not None, "Request has not being processed by HTPP app"
        product_enabled = False
        tags = "_dd.iast.json" if product == "iast" else "_dd.appsec.json"
        meta_struct_key = "iast" if product == "iast" else "appsec"
        spans = list(items[2] for items in interfaces.library.get_spans(request=response))
        logger.debug(f"Found {len(spans)} spans")
        for span in spans:
            # Check if the product is enabled in meta
            meta = span["meta"]
            if tags in meta:
                product_enabled = True
                break
            # Check if the product is enabled in meta_struct
            meta_struct = span["meta_struct"]
            if meta_struct and meta_struct.get(meta_struct_key):
                product_enabled = True
                break
        assert product_enabled, f"{product} is not available"

    @abstractmethod
    def propagated_tag(self):
        return ""  # To be overloaded in final classes

    @abstractmethod
    def propagated_tag_value(self):
        return ""  # To be overloaded in final classes

    def propagated_tag_and_value(self):
        return self.propagated_tag() + "=" + self.propagated_tag_value()

    def setup_product_is_enabled(self, session=None):
        headers = {}
        if self.tested_product == "appsec":
            headers = {
                "User-Agent": "Arachni/v1",  # attack if APPSEC enabled
            }
        self.check_r = session.get(self.request_downstream_url, headers=headers)

    def setup_no_appsec_upstream__no_asm_event__is_kept_with_priority_1__from_minus_1(self):
        with weblog.get_session() as session:
            self.setup_product_is_enabled(session)
            trace_id = 1212121212121212121
            parent_id = 34343434
            self.r = session.get(
                "/requestdownstream",
                headers={
                    "x-datadog-trace-id": str(trace_id),
                    "x-datadog-parent-id": str(parent_id),
                    "x-datadog-sampling-priority": "-1",
                    "x-datadog-origin": "rum",
                    "x-datadog-tags": "_dd.p.other=1",
                },
            )

    @bug(
        condition=(
            context.scenario.name == scenarios.appsec_standalone_api_security.name
            and context.weblog_variant in ("django-poc", "django-py3.13", "python3.12")
        ),
        reason="APPSEC-57830",
    )
    def test_no_appsec_upstream__no_asm_event__is_kept_with_priority_1__from_minus_1(self):
        self.assert_product_is_enabled(self.check_r, self.tested_product)
        spans_checked = 0
        tested_meta = {self.propagated_tag(): None, "_dd.p.other": "1"}
        tested_metrics = {"_sampling_priority_v1": lambda x: x < 2}

        for data, trace, span in interfaces.library.get_spans(request=self.r):
            assert assert_tags(trace[0], span, "meta", tested_meta)
            assert assert_tags(trace[0], span, "metrics", tested_metrics)

            assert span["metrics"]["_dd.apm.enabled"] == 0  # if key missing -> APPSEC-55222
            assert span["trace_id"] == 1212121212121212121
            assert trace[0]["trace_id"] == 1212121212121212121

            # Some tracers use true while others use yes
            assert any(
                header.lower() == "datadog-client-computed-stats" and value.lower() in ["yes", "true"]
                for header, value in data["request"]["headers"]
            )
            spans_checked += 1

        assert spans_checked == 1
        # Downstream propagation is fully disabled in this case
        downstream_headers: CaseInsensitiveDict = CaseInsensitiveDict(json.loads(self.r.text))
        assert "X-Datadog-Origin" not in downstream_headers
        assert "X-Datadog-Parent-Id" not in downstream_headers
        assert "X-Datadog-Tags" not in downstream_headers
        assert "X-Datadog-Sampling-Priority" not in downstream_headers
        assert "X-Datadog-Trace-Id" not in downstream_headers

    def setup_no_appsec_upstream__no_asm_event__is_kept_with_priority_1__from_0(self):
        with weblog.get_session() as session:
            self.setup_product_is_enabled(session)
            trace_id = 1212121212121212121
            parent_id = 34343434
            self.r = session.get(
                "/requestdownstream",
                headers={
                    "x-datadog-trace-id": str(trace_id),
                    "x-datadog-parent-id": str(parent_id),
                    "x-datadog-sampling-priority": "0",
                    "x-datadog-origin": "rum",
                    "x-datadog-tags": "_dd.p.other=1",
                },
            )

    def test_no_appsec_upstream__no_asm_event__is_kept_with_priority_1__from_0(self):
        self.assert_product_is_enabled(self.check_r, self.tested_product)
        spans_checked = 0
        tested_meta = {self.propagated_tag(): None, "_dd.p.other": "1"}
        tested_metrics = {"_sampling_priority_v1": lambda x: x < 2}

        for data, trace, span in interfaces.library.get_spans(request=self.r):
            assert assert_tags(trace[0], span, "meta", tested_meta)
            assert assert_tags(trace[0], span, "metrics", tested_metrics)

            assert span["metrics"]["_dd.apm.enabled"] == 0  # if key missing -> APPSEC-55222
            assert span["trace_id"] == 1212121212121212121
            assert trace[0]["trace_id"] == 1212121212121212121

            # Some tracers use true while others use yes
            assert any(
                header.lower() == "datadog-client-computed-stats" and value.lower() in ["yes", "true"]
                for header, value in data["request"]["headers"]
            )
            spans_checked += 1

        assert spans_checked == 1
        # Downstream propagation is fully disabled in this case
        downstream_headers: CaseInsensitiveDict = CaseInsensitiveDict(json.loads(self.r.text))
        assert "X-Datadog-Origin" not in downstream_headers
        assert "X-Datadog-Parent-Id" not in downstream_headers
        assert "X-Datadog-Tags" not in downstream_headers
        assert "X-Datadog-Sampling-Priority" not in downstream_headers
        assert "X-Datadog-Trace-Id" not in downstream_headers

    def setup_no_appsec_upstream__no_asm_event__is_kept_with_priority_1__from_1(self):
        with weblog.get_session() as session:
            self.setup_product_is_enabled(session)
            trace_id = 1212121212121212121
            parent_id = 34343434
            self.r = session.get(
                "/requestdownstream",
                headers={
                    "x-datadog-trace-id": str(trace_id),
                    "x-datadog-parent-id": str(parent_id),
                    "x-datadog-sampling-priority": "1",
                    "x-datadog-origin": "rum",
                    "x-datadog-tags": "_dd.p.other=1",
                },
            )

    def test_no_appsec_upstream__no_asm_event__is_kept_with_priority_1__from_1(self):
        self.assert_product_is_enabled(self.check_r, self.tested_product)
        spans_checked = 0
        tested_meta = {self.propagated_tag(): None, "_dd.p.other": "1"}
        tested_metrics = {"_sampling_priority_v1": lambda x: x < 2}

        for data, trace, span in interfaces.library.get_spans(request=self.r):
            assert assert_tags(trace[0], span, "meta", tested_meta)
            assert assert_tags(trace[0], span, "metrics", tested_metrics)

            assert span["metrics"]["_dd.apm.enabled"] == 0  # if key missing -> APPSEC-55222
            assert span["trace_id"] == 1212121212121212121
            assert trace[0]["trace_id"] == 1212121212121212121

            # Some tracers use true while others use yes
            assert any(
                header.lower() == "datadog-client-computed-stats" and value.lower() in ["yes", "true"]
                for header, value in data["request"]["headers"]
            )
            spans_checked += 1

        assert spans_checked == 1
        # Downstream propagation is fully disabled in this case
        downstream_headers: CaseInsensitiveDict = CaseInsensitiveDict(json.loads(self.r.text))
        assert "X-Datadog-Origin" not in downstream_headers
        assert "X-Datadog-Parent-Id" not in downstream_headers
        assert "X-Datadog-Tags" not in downstream_headers
        assert "X-Datadog-Sampling-Priority" not in downstream_headers
        assert "X-Datadog-Trace-Id" not in downstream_headers

    def setup_no_appsec_upstream__no_asm_event__is_kept_with_priority_1__from_2(self):
        with weblog.get_session() as session:
            self.setup_product_is_enabled(session)
            trace_id = 1212121212121212121
            parent_id = 34343434
            self.r = session.get(
                "/requestdownstream",
                headers={
                    "x-datadog-trace-id": str(trace_id),
                    "x-datadog-parent-id": str(parent_id),
                    "x-datadog-sampling-priority": "2",
                    "x-datadog-origin": "rum",
                    "x-datadog-tags": "_dd.p.other=1",
                },
            )

    def test_no_appsec_upstream__no_asm_event__is_kept_with_priority_1__from_2(self):
        self.assert_product_is_enabled(self.check_r, self.tested_product)
        spans_checked = 0
        tested_meta = {self.propagated_tag(): None, "_dd.p.other": "1"}
        tested_metrics = {"_sampling_priority_v1": lambda x: x < 2}

        for data, trace, span in interfaces.library.get_spans(request=self.r):
            assert assert_tags(trace[0], span, "meta", tested_meta)
            assert assert_tags(trace[0], span, "metrics", tested_metrics)

            assert span["metrics"]["_dd.apm.enabled"] == 0  # if key missing -> APPSEC-55222
            assert span["trace_id"] == 1212121212121212121
            assert trace[0]["trace_id"] == 1212121212121212121

            # Some tracers use true while others use yes
            assert any(
                header.lower() == "datadog-client-computed-stats" and value.lower() in ["yes", "true"]
                for header, value in data["request"]["headers"]
            )
            spans_checked += 1

        assert spans_checked == 1
        # Downstream propagation is fully disabled in this case
        downstream_headers: CaseInsensitiveDict = CaseInsensitiveDict(json.loads(self.r.text))
        assert "X-Datadog-Origin" not in downstream_headers
        assert "X-Datadog-Parent-Id" not in downstream_headers
        assert "X-Datadog-Tags" not in downstream_headers
        assert "X-Datadog-Sampling-Priority" not in downstream_headers
        assert "X-Datadog-Trace-Id" not in downstream_headers

    def setup_no_upstream_appsec_propagation__with_asm_event__is_kept_with_priority_2__from_minus_1(self):
        trace_id = 1212121212121212121
        parent_id = 34343434
        self.r = weblog.get(
            self.request_downstream_url,
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
                "x-datadog-origin": "rum",
                "x-datadog-sampling-priority": "-1",
                "x-datadog-tags": "_dd.p.other=1",
                "User-Agent": "Arachni/v1",  # attack if APPSEC enabled
            },
        )

    def test_no_upstream_appsec_propagation__with_asm_event__is_kept_with_priority_2__from_minus_1(self):
        spans_checked = 0
        tested_meta = {self.propagated_tag(): self.propagated_tag_value()}
        tested_metrics = {"_sampling_priority_v1": lambda x: x == 2}

        for data, trace, span in interfaces.library.get_spans(request=self.r):
            assert assert_tags(trace[0], span, "meta", tested_meta)
            assert assert_tags(trace[0], span, "metrics", tested_metrics)

            assert span["metrics"]["_dd.apm.enabled"] == 0  # if key missing -> APPSEC-55222
            assert span["trace_id"] == 1212121212121212121
            assert trace[0]["trace_id"] == 1212121212121212121

            # Some tracers use true while others use yes
            assert any(
                header.lower() == "datadog-client-computed-stats" and value.lower() in ["yes", "true"]
                for header, value in data["request"]["headers"]
            )
            spans_checked += 1

        assert spans_checked == 1
        downstream_headers: CaseInsensitiveDict = CaseInsensitiveDict(json.loads(self.r.text))
        assert downstream_headers["X-Datadog-Origin"] == "rum"
        assert downstream_headers["X-Datadog-Parent-Id"] != "34343434"
        assert "_dd.p.other=1" in downstream_headers["X-Datadog-Tags"]
        assert self.propagated_tag_and_value() in downstream_headers["X-Datadog-Tags"]
        assert downstream_headers["X-Datadog-Sampling-Priority"] == "2"
        assert downstream_headers["X-Datadog-Trace-Id"] == "1212121212121212121"

    def setup_no_upstream_appsec_propagation__with_asm_event__is_kept_with_priority_2__from_0(self):
        trace_id = 1212121212121212121
        parent_id = 34343434
        self.r = weblog.get(
            self.request_downstream_url,
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
                "x-datadog-origin": "rum",
                "x-datadog-sampling-priority": "0",
                "x-datadog-tags": "_dd.p.other=1",
                "User-Agent": "Arachni/v1",  # attack if APPSEC enabled
            },
        )

    def test_no_upstream_appsec_propagation__with_asm_event__is_kept_with_priority_2__from_0(self):
        spans_checked = 0
        tested_meta = {self.propagated_tag(): self.propagated_tag_value()}
        tested_metrics = {"_sampling_priority_v1": lambda x: x == 2}

        for data, trace, span in interfaces.library.get_spans(request=self.r):
            assert assert_tags(trace[0], span, "meta", tested_meta)
            assert assert_tags(trace[0], span, "metrics", tested_metrics)

            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert span["trace_id"] == 1212121212121212121
            assert trace[0]["trace_id"] == 1212121212121212121

            # Some tracers use true while others use yes
            assert any(
                header.lower() == "datadog-client-computed-stats" and value.lower() in ["yes", "true"]
                for header, value in data["request"]["headers"]
            )
            spans_checked += 1

        assert spans_checked == 1
        downstream_headers: CaseInsensitiveDict = CaseInsensitiveDict(json.loads(self.r.text))
        assert downstream_headers["X-Datadog-Origin"] == "rum"
        assert downstream_headers["X-Datadog-Parent-Id"] != "34343434"
        assert "_dd.p.other=1" in downstream_headers["X-Datadog-Tags"]
        assert self.propagated_tag_and_value() in downstream_headers["X-Datadog-Tags"]
        assert downstream_headers["X-Datadog-Sampling-Priority"] == "2"
        assert downstream_headers["X-Datadog-Trace-Id"] == "1212121212121212121"

    def setup_upstream_appsec_propagation__no_asm_event__is_propagated_as_is__being_0(self):
        with weblog.get_session() as session:
            self.setup_product_is_enabled(session)
            trace_id = 1212121212121212121
            parent_id = 34343434
            self.r = session.get(
                "/requestdownstream",
                headers={
                    "x-datadog-trace-id": str(trace_id),
                    "x-datadog-parent-id": str(parent_id),
                    "x-datadog-origin": "rum",
                    "x-datadog-sampling-priority": "0",
                    "x-datadog-tags": self.propagated_tag_and_value(),
                },
            )

    def test_upstream_appsec_propagation__no_asm_event__is_propagated_as_is__being_0(self):
        self.assert_product_is_enabled(self.check_r, self.tested_product)
        spans_checked = 0
        tested_meta = {self.propagated_tag(): self.propagated_tag_value()}
        tested_metrics = {"_sampling_priority_v1": lambda x: x in [0, 2]}

        for data, trace, span in interfaces.library.get_spans(request=self.r):
            assert assert_tags(trace[0], span, "meta", tested_meta)
            assert assert_tags(trace[0], span, "metrics", tested_metrics)

            assert span["metrics"]["_dd.apm.enabled"] == 0  # if key missing -> APPSEC-55222
            assert span["trace_id"] == 1212121212121212121
            assert trace[0]["trace_id"] == 1212121212121212121

            # Some tracers use true while others use yes
            assert any(
                header.lower() == "datadog-client-computed-stats" and value.lower() in ["yes", "true"]
                for header, value in data["request"]["headers"]
            )
            spans_checked += 1

        assert spans_checked == 1
        downstream_headers: CaseInsensitiveDict = CaseInsensitiveDict(json.loads(self.r.text))
        assert downstream_headers["X-Datadog-Origin"] == "rum"
        assert downstream_headers["X-Datadog-Parent-Id"] != "34343434"
        assert self.propagated_tag_and_value() in downstream_headers["X-Datadog-Tags"]
        assert downstream_headers["X-Datadog-Sampling-Priority"] in ["0", "2"]
        assert downstream_headers["X-Datadog-Trace-Id"] == "1212121212121212121"

    def setup_upstream_appsec_propagation__no_asm_event__is_propagated_as_is__being_1(self):
        with weblog.get_session() as session:
            self.setup_product_is_enabled(session)
            trace_id = 1212121212121212121
            parent_id = 34343434
            self.r = session.get(
                "/requestdownstream",
                headers={
                    "x-datadog-trace-id": str(trace_id),
                    "x-datadog-parent-id": str(parent_id),
                    "x-datadog-origin": "rum",
                    "x-datadog-sampling-priority": "1",
                    "x-datadog-tags": self.propagated_tag_and_value(),
                },
            )

    def test_upstream_appsec_propagation__no_asm_event__is_propagated_as_is__being_1(self):
        self.assert_product_is_enabled(self.check_r, self.tested_product)
        spans_checked = 0
        tested_meta = {self.propagated_tag(): self.propagated_tag_value()}
        tested_metrics = {"_sampling_priority_v1": lambda x: x in [1, 2]}

        for data, trace, span in interfaces.library.get_spans(request=self.r):
            assert assert_tags(trace[0], span, "meta", tested_meta)
            assert assert_tags(trace[0], span, "metrics", tested_metrics)

            assert span["metrics"]["_dd.apm.enabled"] == 0  # if key missing -> APPSEC-55222
            assert span["trace_id"] == 1212121212121212121
            assert trace[0]["trace_id"] == 1212121212121212121

            # Some tracers use true while others use yes
            assert any(
                header.lower() == "datadog-client-computed-stats" and value.lower() in ["yes", "true"]
                for header, value in data["request"]["headers"]
            )
            spans_checked += 1

        assert spans_checked == 1
        downstream_headers: CaseInsensitiveDict = CaseInsensitiveDict(json.loads(self.r.text))
        assert downstream_headers["X-Datadog-Origin"] == "rum"
        assert downstream_headers["X-Datadog-Parent-Id"] != "34343434"
        assert self.propagated_tag_and_value() in downstream_headers["X-Datadog-Tags"]
        assert downstream_headers["X-Datadog-Sampling-Priority"] in ["1", "2"]
        assert downstream_headers["X-Datadog-Trace-Id"] == "1212121212121212121"

    def setup_upstream_appsec_propagation__no_asm_event__is_propagated_as_is__being_2(self):
        with weblog.get_session() as session:
            self.setup_product_is_enabled(session)
            trace_id = 1212121212121212121
            parent_id = 34343434
            self.r = session.get(
                "/requestdownstream",
                headers={
                    "x-datadog-trace-id": str(trace_id),
                    "x-datadog-parent-id": str(parent_id),
                    "x-datadog-origin": "rum",
                    "x-datadog-sampling-priority": "2",
                    "x-datadog-tags": self.propagated_tag_and_value(),
                },
            )

    def test_upstream_appsec_propagation__no_asm_event__is_propagated_as_is__being_2(self):
        self.assert_product_is_enabled(self.check_r, self.tested_product)
        spans_checked = 0
        tested_meta = {self.propagated_tag(): self.propagated_tag_value()}
        tested_metrics = {"_sampling_priority_v1": lambda x: x == 2}

        for data, trace, span in interfaces.library.get_spans(request=self.r):
            assert assert_tags(trace[0], span, "meta", tested_meta)
            assert assert_tags(trace[0], span, "metrics", tested_metrics)

            assert span["metrics"]["_dd.apm.enabled"] == 0  # if key missing -> APPSEC-55222
            assert span["trace_id"] == 1212121212121212121
            assert trace[0]["trace_id"] == 1212121212121212121

            # Some tracers use true while others use yes
            assert any(
                header.lower() == "datadog-client-computed-stats" and value.lower() in ["yes", "true"]
                for header, value in data["request"]["headers"]
            )
            spans_checked += 1

        assert spans_checked == 1
        downstream_headers: CaseInsensitiveDict = CaseInsensitiveDict(json.loads(self.r.text))
        assert downstream_headers["X-Datadog-Origin"] == "rum"
        assert downstream_headers["X-Datadog-Parent-Id"] != "34343434"
        assert self.propagated_tag_and_value() in downstream_headers["X-Datadog-Tags"]
        assert downstream_headers["X-Datadog-Sampling-Priority"] == "2"
        assert downstream_headers["X-Datadog-Trace-Id"] == "1212121212121212121"

    def setup_any_upstream_propagation__with_asm_event__raises_priority_to_2__from_minus_1(self):
        trace_id = 1212121212121212121
        parent_id = 34343434
        self.r = weblog.get(
            self.request_downstream_url,
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
                "x-datadog-origin": "rum",
                "x-datadog-sampling-priority": "-1",
                "User-Agent": "Arachni/v1",  # attack if APPSEC enabled
            },
        )

    def test_any_upstream_propagation__with_asm_event__raises_priority_to_2__from_minus_1(self):
        spans_checked = 0
        tested_meta = {self.propagated_tag(): self.propagated_tag_value()}
        tested_metrics = {"_sampling_priority_v1": lambda x: x == 2}

        for data, trace, span in interfaces.library.get_spans(request=self.r):
            assert assert_tags(trace[0], span, "meta", tested_meta)
            assert assert_tags(trace[0], span, "metrics", tested_metrics)

            assert span["metrics"]["_dd.apm.enabled"] == 0  # if key missing -> APPSEC-55222
            assert span["trace_id"] == 1212121212121212121
            assert trace[0]["trace_id"] == 1212121212121212121

            # Some tracers use true while others use yes
            assert any(
                header.lower() == "datadog-client-computed-stats" and value.lower() in ["yes", "true"]
                for header, value in data["request"]["headers"]
            )
            spans_checked += 1

        assert spans_checked == 1
        downstream_headers: CaseInsensitiveDict = CaseInsensitiveDict(json.loads(self.r.text))
        assert downstream_headers["X-Datadog-Origin"] == "rum"
        assert downstream_headers["X-Datadog-Parent-Id"] != "34343434"
        assert self.propagated_tag_and_value() in downstream_headers["X-Datadog-Tags"]
        assert downstream_headers["X-Datadog-Sampling-Priority"] == "2"
        assert downstream_headers["X-Datadog-Trace-Id"] == "1212121212121212121"

    def setup_any_upstream_propagation__with_asm_event__raises_priority_to_2__from_0(self):
        trace_id = 1212121212121212121
        parent_id = 34343434
        self.r = weblog.get(
            self.request_downstream_url,
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
                "x-datadog-origin": "rum",
                "x-datadog-sampling-priority": "0",
                "User-Agent": "Arachni/v1",
            },
        )

    def test_any_upstream_propagation__with_asm_event__raises_priority_to_2__from_0(self):
        spans_checked = 0
        tested_meta = {self.propagated_tag(): self.propagated_tag_value()}
        tested_metrics = {"_sampling_priority_v1": lambda x: x == 2}

        for data, trace, span in interfaces.library.get_spans(request=self.r):
            assert assert_tags(trace[0], span, "meta", tested_meta)
            assert assert_tags(trace[0], span, "metrics", tested_metrics)

            assert span["metrics"]["_dd.apm.enabled"] == 0  # if key missing -> APPSEC-55222
            assert span["trace_id"] == 1212121212121212121
            assert trace[0]["trace_id"] == 1212121212121212121

            # Some tracers use true while others use yes
            assert any(
                header.lower() == "datadog-client-computed-stats" and value.lower() in ["yes", "true"]
                for header, value in data["request"]["headers"]
            )
            spans_checked += 1

        assert spans_checked == 1
        downstream_headers: CaseInsensitiveDict = CaseInsensitiveDict(json.loads(self.r.text))
        assert downstream_headers["X-Datadog-Origin"] == "rum"
        assert downstream_headers["X-Datadog-Parent-Id"] != "34343434"
        assert self.propagated_tag_and_value() in downstream_headers["X-Datadog-Tags"]
        assert downstream_headers["X-Datadog-Sampling-Priority"] == "2"
        assert downstream_headers["X-Datadog-Trace-Id"] == "1212121212121212121"

    def setup_any_upstream_propagation__with_asm_event__raises_priority_to_2__from_1(self):
        trace_id = 1212121212121212121
        parent_id = 34343434
        self.r = weblog.get(
            self.request_downstream_url,
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
                "x-datadog-origin": "rum",
                "x-datadog-sampling-priority": "1",
                "User-Agent": "Arachni/v1",  # attack if APPSEC enabled
            },
        )

    def test_any_upstream_propagation__with_asm_event__raises_priority_to_2__from_1(self):
        spans_checked = 0
        tested_meta = {self.propagated_tag(): self.propagated_tag_value()}
        tested_metrics = {"_sampling_priority_v1": lambda x: x == 2}

        for data, trace, span in interfaces.library.get_spans(request=self.r):
            assert assert_tags(trace[0], span, "meta", tested_meta)
            assert assert_tags(trace[0], span, "metrics", tested_metrics)

            assert span["metrics"]["_dd.apm.enabled"] == 0  # if key missing -> APPSEC-55222
            assert span["trace_id"] == 1212121212121212121
            assert trace[0]["trace_id"] == 1212121212121212121

            # Some tracers use true while others use yes
            assert any(
                header.lower() == "datadog-client-computed-stats" and value.lower() in ["yes", "true"]
                for header, value in data["request"]["headers"]
            )
            spans_checked += 1

        assert spans_checked == 1
        downstream_headers: CaseInsensitiveDict = CaseInsensitiveDict(json.loads(self.r.text))
        assert downstream_headers["X-Datadog-Origin"] == "rum"
        assert downstream_headers["X-Datadog-Parent-Id"] != "34343434"
        assert self.propagated_tag_and_value() in downstream_headers["X-Datadog-Tags"]
        assert downstream_headers["X-Datadog-Sampling-Priority"] == "2"
        assert downstream_headers["X-Datadog-Trace-Id"] == "1212121212121212121"


class BaseAppSecStandaloneUpstreamPropagation(BaseAsmStandaloneUpstreamPropagation):
    """APPSEC correctly propagates AppSec events in distributing tracing."""

    request_downstream_url: str = "/requestdownstream"
    tested_product: str = "appsec"

    @bug(library="java", weblog_variant="akka-http", reason="APPSEC-55001")
    @bug(library="java", weblog_variant="jersey-grizzly2", reason="APPSEC-55001")
    @bug(library="java", weblog_variant="play", reason="APPSEC-55001")
    def test_no_upstream_appsec_propagation__with_asm_event__is_kept_with_priority_2__from_minus_1(self):
        super().test_no_upstream_appsec_propagation__with_asm_event__is_kept_with_priority_2__from_minus_1()

    @bug(library="java", weblog_variant="akka-http", reason="APPSEC-55001")
    @bug(library="java", weblog_variant="jersey-grizzly2", reason="APPSEC-55001")
    @bug(library="java", weblog_variant="play", reason="APPSEC-55001")
    def test_no_upstream_appsec_propagation__with_asm_event__is_kept_with_priority_2__from_0(self):
        super().test_no_upstream_appsec_propagation__with_asm_event__is_kept_with_priority_2__from_0()

    @bug(library="java", weblog_variant="akka-http", reason="APPSEC-55001")
    @bug(library="java", weblog_variant="jersey-grizzly2", reason="APPSEC-55001")
    @bug(library="java", weblog_variant="play", reason="APPSEC-55001")
    def test_any_upstream_propagation__with_asm_event__raises_priority_to_2__from_minus_1(self):
        super().test_any_upstream_propagation__with_asm_event__raises_priority_to_2__from_minus_1()

    @bug(library="java", weblog_variant="akka-http", reason="APPSEC-55001")
    @bug(library="java", weblog_variant="jersey-grizzly2", reason="APPSEC-55001")
    @bug(library="java", weblog_variant="play", reason="APPSEC-55001")
    def test_any_upstream_propagation__with_asm_event__raises_priority_to_2__from_0(self):
        super().test_any_upstream_propagation__with_asm_event__raises_priority_to_2__from_0()

    @bug(library="java", weblog_variant="akka-http", reason="APPSEC-55001")
    @bug(library="java", weblog_variant="jersey-grizzly2", reason="APPSEC-55001")
    @bug(library="java", weblog_variant="play", reason="APPSEC-55001")
    def test_any_upstream_propagation__with_asm_event__raises_priority_to_2__from_1(self):
        super().test_any_upstream_propagation__with_asm_event__raises_priority_to_2__from_1()


class BaseIastStandaloneUpstreamPropagation(BaseAsmStandaloneUpstreamPropagation):
    """IAST correctly propagates AppSec events in distributing tracing."""

    request_downstream_url = "/vulnerablerequestdownstream"

    tested_product = "iast"

    @bug(library="java", weblog_variant="play", reason="APPSEC-55552")
    def test_no_appsec_upstream__no_asm_event__is_kept_with_priority_1__from_minus_1(self):
        super().test_no_appsec_upstream__no_asm_event__is_kept_with_priority_1__from_minus_1()

    @bug(library="java", weblog_variant="play", reason="APPSEC-55552")
    def test_no_appsec_upstream__no_asm_event__is_kept_with_priority_1__from_0(self):
        super().test_no_appsec_upstream__no_asm_event__is_kept_with_priority_1__from_0()

    @bug(library="java", weblog_variant="play", reason="APPSEC-55552")
    def test_no_appsec_upstream__no_asm_event__is_kept_with_priority_1__from_1(self):
        super().test_no_appsec_upstream__no_asm_event__is_kept_with_priority_1__from_1()

    @bug(library="java", weblog_variant="play", reason="APPSEC-55552")
    def test_no_appsec_upstream__no_asm_event__is_kept_with_priority_1__from_2(self):
        super().test_no_appsec_upstream__no_asm_event__is_kept_with_priority_1__from_2()


class BaseSCAStandaloneTelemetry:
    """Tracer correctly propagates SCA telemetry in distributing tracing."""

    def assert_standalone_is_enabled(self, request0, request1):
        # test standalone is enabled and dropping traces
        spans_checked = 0
        for _, __, span in list(interfaces.library.get_spans(request0)) + list(interfaces.library.get_spans(request1)):
            if span["metrics"]["_sampling_priority_v1"] <= 0 and span["metrics"]["_dd.apm.enabled"] == 0:
                spans_checked += 1

        assert spans_checked > 0

    def setup_telemetry_sca_enabled_propagated(self):
        # It's not possible to ensure first request will not be used as standalone heartbeat so let's do two just in case
        self.r0 = weblog.get("/")
        self.r1 = weblog.get("/")

    def test_telemetry_sca_enabled_propagated(self):
        self.assert_standalone_is_enabled(self.r0, self.r1)

        configuration_by_name: dict[str, dict] = {}
        for data in interfaces.library.get_telemetry_data():
            content = data["request"]["content"]
            if content.get("request_type") != "app-started":
                continue
            configuration = content["payload"]["configuration"]

            configuration_by_name = {**configuration_by_name, **{item["name"]: item for item in configuration}}

        assert configuration_by_name

        dd_appsec_sca_enabled = TelemetryUtils.get_dd_appsec_sca_enabled_str(context.library)

        cfg_appsec_enabled = configuration_by_name.get(dd_appsec_sca_enabled)
        assert cfg_appsec_enabled is not None, f"Missing telemetry config item for '{dd_appsec_sca_enabled}'"

        outcome_value: bool | str = True
        if context.library in ["java", "php"]:
            outcome_value = str(outcome_value).lower()
        assert cfg_appsec_enabled.get("value") == outcome_value

    def setup_app_dependencies_loaded(self):
        # It's not possible to ensure first request will not be used as standalone heartbeat so let's do two just in case
        self.r0 = weblog.get("/load_dependency")
        self.r1 = weblog.get("/load_dependency")

    @irrelevant(context.library == "golang", reason="Go does not support dynamic dependency loading")
    @missing_feature(context.library == "nodejs" and context.weblog_variant == "nextjs")
    @missing_feature(context.weblog_variant == "vertx4", reason="missing_feature (endpoint not implemented)")
    @missing_feature(context.weblog_variant == "akka-http", reason="missing_feature (endpoint not implemented)")
    @missing_feature(context.weblog_variant == "ratpack", reason="missing_feature (endpoint not implemented)")
    @missing_feature(context.weblog_variant == "play", reason="missing_feature (endpoint not implemented)")
    @missing_feature(context.weblog_variant == "vertx3", reason="missing_feature (endpoint not implemented)")
    @missing_feature(context.weblog_variant == "jersey-grizzly2", reason="missing_feature (endpoint not implemented)")
    def test_app_dependencies_loaded(self):
        self.assert_standalone_is_enabled(self.r0, self.r1)

        seen_loaded_dependencies = TelemetryUtils.get_loaded_dependency(context.library.name)

        for data in interfaces.library.get_telemetry_data():
            content = data["request"]["content"]
            if content.get("request_type") != "app-dependencies-loaded":
                continue

            for dependency in content["payload"]["dependencies"]:
                dependency_id = dependency["name"]  # +dependency["version"]

                if dependency_id in seen_loaded_dependencies:
                    seen_loaded_dependencies[dependency_id] = True

        for dependency, seen in seen_loaded_dependencies.items():
            if not seen:
                raise Exception(dependency + " not received in app-dependencies-loaded message")


@rfc("https://docs.google.com/document/d/12NBx-nD-IoQEMiCRnJXneq4Be7cbtSc6pJLOFUWTpNE/edit")
@features.appsec_standalone
class Test_AppSecStandalone_NotEnabled:
    """Test expected behaviour when standalone is not enabled."""

    def setup_client_computed_stats_header_is_not_present(self):
        trace_id = 1212121212121212122
        parent_id = 34343434
        self.r = weblog.get(
            "/",
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
            },
        )

    def test_client_computed_stats_header_is_not_present(self):
        spans_checked = 0
        for data, _, span in interfaces.library.get_spans(request=self.r):
            assert span["trace_id"] == 1212121212121212122
            assert "datadog-client-computed-stats" not in [x.lower() for x, y in data["request"]["headers"]]
            spans_checked += 1
        assert spans_checked == 1


@rfc("https://docs.google.com/document/d/12NBx-nD-IoQEMiCRnJXneq4Be7cbtSc6pJLOFUWTpNE/edit")
@features.appsec_standalone_experimental
@scenarios.appsec_standalone_experimental
@irrelevant(context.library > "java@v1.46.0", reason="V2 is implemented for newer versions")
class Test_AppSecStandalone_UpstreamPropagation(BaseAppSecStandaloneUpstreamPropagation):
    """APPSEC correctly propagates AppSec events in distributing tracing with DD_EXPERIMENTAL_APPSEC_STANDALONE_ENABLED=true."""

    def propagated_tag(self):
        return "_dd.p.appsec"

    def propagated_tag_value(self):
        return "1"


@rfc("https://docs.google.com/document/d/12NBx-nD-IoQEMiCRnJXneq4Be7cbtSc6pJLOFUWTpNE/edit")
@features.appsec_standalone
@scenarios.appsec_standalone
class Test_AppSecStandalone_UpstreamPropagation_V2(BaseAppSecStandaloneUpstreamPropagation):
    """APPSEC correctly propagates AppSec events in distributing tracing with DD_APM_TRACING_ENABLED=false."""

    def propagated_tag(self):
        return "_dd.p.ts"

    def propagated_tag_value(self):
        return "02"


@rfc("https://docs.google.com/document/d/12NBx-nD-IoQEMiCRnJXneq4Be7cbtSc6pJLOFUWTpNE/edit")
@features.iast_standalone_experimental
@scenarios.iast_standalone_experimental
@irrelevant(context.library > "java@v1.46.0", reason="V2 is implemented for newer versions")
class Test_IastStandalone_UpstreamPropagation(BaseIastStandaloneUpstreamPropagation):
    """IAST correctly propagates AppSec events in distributing tracing with DD_EXPERIMENTAL_APPSEC_STANDALONE_ENABLED=true."""

    def propagated_tag(self):
        return "_dd.p.appsec"

    def propagated_tag_value(self):
        return "1"


@rfc("https://docs.google.com/document/d/12NBx-nD-IoQEMiCRnJXneq4Be7cbtSc6pJLOFUWTpNE/edit")
@features.iast_standalone
@scenarios.iast_standalone
@flaky(context.library >= "python@3.10.1", reason="APPSEC-58276")
class Test_IastStandalone_UpstreamPropagation_V2(BaseIastStandaloneUpstreamPropagation):
    """IAST correctly propagates AppSec events in distributing tracing with DD_APM_TRACING_ENABLED=false."""

    def propagated_tag(self):
        return "_dd.p.ts"

    def propagated_tag_value(self):
        return "02"


@rfc("https://docs.google.com/document/d/12NBx-nD-IoQEMiCRnJXneq4Be7cbtSc6pJLOFUWTpNE/edit")
@features.sca_standalone_experimental
@scenarios.sca_standalone_experimental
@irrelevant(context.library > "java@v1.46.0", reason="V2 is implemented for newer versions")
class Test_SCAStandalone_Telemetry(BaseSCAStandaloneTelemetry):
    """Tracer correctly propagates SCA telemetry in distributing tracing with DD_EXPERIMENTAL_APPSEC_STANDALONE_ENABLED=true."""

    def propagated_tag(self):
        return "_dd.p.appsec"

    def propagated_tag_value(self):
        return "1"


@rfc("https://docs.google.com/document/d/12NBx-nD-IoQEMiCRnJXneq4Be7cbtSc6pJLOFUWTpNE/edit")
@features.sca_standalone
@scenarios.sca_standalone
class Test_SCAStandalone_Telemetry_V2(BaseSCAStandaloneTelemetry):
    """Tracer correctly propagates SCA telemetry in distributing tracing with DD_APM_TRACING_ENABLED=false."""

    def propagated_tag(self):
        return "_dd.p.ts"

    def propagated_tag_value(self):
        return "02"


@rfc("https://docs.google.com/document/d/18JZdOS5fmnYomRn6OGer0ViS1I6zzT6xl5HMtjDtFn4/edit")
@features.api_security_configuration
@scenarios.appsec_standalone_api_security
@flaky(context.library > "java@1.49.0", reason="APPSEC-57815")
class Test_APISecurityStandalone(BaseAppSecStandaloneUpstreamPropagation):
    """Test API Security schemas are retained in ASM Standalone mode regardless of sampling"""

    def propagated_tag(self):
        return "_dd.p.ts"

    def propagated_tag_value(self):
        return "02"

    @staticmethod
    def get_schema(request, address) -> list | None:
        """Extract API security schema from span metadata"""
        for _, _, span in interfaces.library.get_spans(request=request):
            meta = span.get("meta", {})
            if payload := meta.get("_dd.appsec.s." + address):
                return payload
        return None

    @staticmethod
    def check_trace_retained(request, *, should_be_retained: bool) -> bool:
        """Check if trace is retained with expected sampling priority"""

        spans_checked = 0
        tested_metrics = {"_sampling_priority_v1": lambda x: x == 2 if should_be_retained else x <= 0}
        for data, trace, span in interfaces.library.get_spans(request=request):
            assert span["trace_id"] == 1212121212121212121
            assert trace[0]["trace_id"] == 1212121212121212121
            assert assert_tags(trace[0], span, "metrics", tested_metrics)
            assert span["metrics"]["_dd.apm.enabled"] == 0  # if key missing -> APPSEC-55222

            # Check for client-computed-stats header
            headers = data["request"]["headers"]
            assert any(
                header.lower() == "datadog-client-computed-stats" and value.lower() in ["yes", "true"]
                for header, value in headers
            )
            spans_checked += 1

        return spans_checked == 1

    def verify_trace_sampling(self, request, *, should_be_retained: bool, should_have_schema: bool):
        """Verify trace is sampled with expected sampling priority and schema presence

        Args:
            request: The HTTP request to verify
            should_be_retained: Whether the trace should be retained
            should_have_schema: Whether schema should exist in the trace

        """

        assert self.check_trace_retained(request, should_be_retained=should_be_retained), "Trace retention check failed"
        schema = self.get_schema(request, "req.headers")

        if should_have_schema:
            assert schema is not None, "Schema missing when it should exist"
            assert isinstance(schema, list), "Schema has invalid format"
            for header in ("host", "user-agent"):
                assert header in schema[0], f"Header '{header}' missing from schema"
                assert isinstance(schema[0][header], list), f"Header '{header}' value is not a list"
        else:
            assert schema is None, "Schema found when it should be absent"

    def _get_headers(self, trace_id=1212121212121212121):
        """Standard test headers"""
        return {
            "x-datadog-trace-id": str(trace_id),
            "x-datadog-parent-id": "34343434",
            "x-datadog-origin": "rum",
            "x-datadog-sampling-priority": "-1",
        }

    def setup_first_request_retained(self):
        endpoint = "/tag_value/test_first_request_retained/200"
        self.first_request = weblog.get(endpoint, headers=self._get_headers())

    def test_first_request_retained(self):
        assert self.first_request.status_code == 200
        self.verify_trace_sampling(self.first_request, should_be_retained=True, should_have_schema=True)

    def setup_different_endpoints(self):
        with weblog.get_session() as session:
            self.request1 = session.get("/api_security/sampling/200", headers=self._get_headers())
            self.request2 = session.get("/api_security_sampling/1", headers=self._get_headers())
            self.subsequent_requests = [
                session.get("/api_security/sampling/200", headers=self._get_headers()) for _ in range(5)
            ]

    def test_different_endpoints(self):
        # First requests to different endpoints retained with schema
        assert self.request1.status_code == 200
        self.verify_trace_sampling(self.request1, should_be_retained=True, should_have_schema=True)

        assert self.request2.status_code == 200
        self.verify_trace_sampling(self.request2, should_be_retained=True, should_have_schema=True)

        # Subsequent requests to same endpoint sampled out
        for request in self.subsequent_requests:
            assert request.status_code == 200
            self.verify_trace_sampling(request, should_be_retained=False, should_have_schema=False)

    def setup_sampling_window_renewal(self):
        time.sleep(4)  # Wait for the sampling window to expire

        self.endpoint = "/api_security/sampling/200"

        with weblog.get_session() as session:
            self.window1_request1 = session.get(self.endpoint, headers=self._get_headers())
            self.window1_request2 = session.get(self.endpoint, headers=self._get_headers())
            time.sleep(4)  # Delay is set to 3s via the env var DD_API_SECURITY_SAMPLE_DELAY
            self.window2_request1 = session.get(self.endpoint, headers=self._get_headers())

    def test_sampling_window_renewal(self):
        """Verify that endpoint sampling resets after the sampling window expires"""

        # First request should be retained with schema
        assert self.window1_request1.status_code == 200
        self.verify_trace_sampling(self.window1_request1, should_be_retained=True, should_have_schema=True)

        # Following request sampled out
        assert self.window1_request2.status_code == 200
        self.verify_trace_sampling(self.window1_request2, should_be_retained=False, should_have_schema=False)

        # After window expiration, request retained again
        assert self.window2_request1.status_code == 200
        self.verify_trace_sampling(self.window2_request1, should_be_retained=True, should_have_schema=True)

    def setup_appsec_propagation_does_not_force_schema_collection(self):
        """Test that spans with USER_KEEP priority do not force schema collection"""

        time.sleep(4)  # Wait for the sampling window to expire

        self.endpoint = "/api_security/sampling/200"

        # Set USER_KEEP (2) priority explicitly
        headers = self._get_headers()
        headers["x-datadog-sampling-priority"] = "2"  # USER_KEEP
        headers["x-datadog-tags"] = f"{self.propagated_tag()}={self.propagated_tag_value()}"

        # Make multiple requests to same endpoint that would normally be sampled out
        with weblog.get_session() as session:
            self.request1 = session.get(self.endpoint, headers=headers)
            self.request2 = session.get(self.endpoint, headers=headers)
            self.request3 = session.get(self.endpoint, headers=headers)

    def test_appsec_propagation_does_not_force_schema_collection(self):
        """Test that spans with USER_KEEP priority do not force schema collection"""

        assert self.request1.status_code == 200
        self.verify_trace_sampling(self.request1, should_be_retained=True, should_have_schema=True)

        assert self.request2.status_code == 200
        self.verify_trace_sampling(self.request2, should_be_retained=True, should_have_schema=False)

        assert self.request3.status_code == 200
        self.verify_trace_sampling(self.request3, should_be_retained=True, should_have_schema=False)


@rfc("https://docs.google.com/document/d/18JZdOS5fmnYomRn6OGer0ViS1I6zzT6xl5HMtjDtFn4/edit")
@features.appsec_standalone
@scenarios.appsec_standalone
class Test_UserEventsStandalone_Automated:
    """IAST correctly propagates user events in distributing tracing with DD_APM_TRACING_ENABLED=false."""

    def _get_test_headers(self, trace_id):
        return {
            "x-datadog-trace-id": str(trace_id),
            "x-datadog-parent-id": str(34343434),
            "x-datadog-origin": "rum",
            "x-datadog-sampling-priority": "-1",
            "x-datadog-tags": "_dd.p.other=1",
        }

    def _login_data(self, context, user, password):
        """In Rails the parameters are group by scope. In the case of the test the scope is user.
        The syntax to group parameters in a POST request is scope[parameter]
        """
        username_key = "user[username]" if "rails" in context.weblog_variant else "username"
        password_key = "user[password]" if "rails" in context.weblog_variant else "password"
        return {username_key: user, password_key: password}

    def _get_standalone_span_meta(self, trace_id):
        tested_meta = {
            "_dd.p.ts": "02",
        }
        for data, trace, span in interfaces.library.get_spans(request=self.r):
            assert assert_tags(trace[0], span, "meta", tested_meta)

            assert span["metrics"]["_dd.apm.enabled"] == 0  # if key missing -> APPSEC-55222
            assert span["trace_id"] == trace_id
            assert trace[0]["trace_id"] == trace_id

            # Some tracers use true while others use yes
            assert any(
                header.lower() == "datadog-client-computed-stats" and value.lower() in ["yes", "true"]
                for header, value in data["request"]["headers"]
            )
            return span["meta"]

        return None

    def _call_endpoint(self, endpoint, user, trace_id):
        self.r = weblog.post(
            endpoint,
            headers=self._get_test_headers(trace_id),
            data=self._login_data(context, user, PASSWORD),
        )

    def setup_user_login_success_event_generates_asm_event(self):
        trace_id = 1212121212121212111
        self._call_endpoint("/login?auth=local", USER, trace_id)

    def test_user_login_success_event_generates_asm_event(self):
        trace_id = 1212121212121212111
        meta = self._get_standalone_span_meta(trace_id)
        assert meta is not None
        assert meta["_dd.appsec.usr.login"] == USER

    def setup_user_login_failure_event_generates_asm_event(self):
        trace_id = 1212121212121212122
        self._call_endpoint("/login?auth=local", INVALID_USER, trace_id)

    def test_user_login_failure_event_generates_asm_event(self):
        trace_id = 1212121212121212122
        meta = self._get_standalone_span_meta(trace_id)
        assert meta is not None
        assert meta["_dd.appsec.usr.login"] == INVALID_USER

    def setup_user_signup_event_generates_asm_event(self):
        trace_id = 1212121212121212133
        self._call_endpoint("/signup", NEW_USER, trace_id)

    @irrelevant(
        context.library == "python" and context.weblog_variant not in ["django-poc", "python3.12", "django-py3.13"],
        reason="no signup events in Python except for django",
    )
    @missing_feature(context.library == "nodejs", reason="no signup events in passport")
    def test_user_signup_event_generates_asm_event(self):
        trace_id = 1212121212121212133
        meta = self._get_standalone_span_meta(trace_id)
        assert meta is not None
        assert meta["appsec.events.users.signup.usr.login"] == NEW_USER


@rfc("https://docs.google.com/document/d/18JZdOS5fmnYomRn6OGer0ViS1I6zzT6xl5HMtjDtFn4/edit")
@features.appsec_standalone
@scenarios.appsec_standalone
class Test_UserEventsStandalone_SDK_V1:
    """IAST correctly propagates user events in distributing tracing with DD_APM_TRACING_ENABLED=false."""

    def _get_test_headers(self, trace_id):
        return {
            "x-datadog-trace-id": str(trace_id),
            "x-datadog-parent-id": str(34343434),
            "x-datadog-origin": "rum",
            "x-datadog-sampling-priority": "-1",
            "x-datadog-tags": "_dd.p.other=1",
        }

    def _get_standalone_span_meta(self, trace_id):
        tested_meta = {
            "_dd.p.ts": "02",
        }
        for data, trace, span in interfaces.library.get_spans(request=self.r):
            assert assert_tags(trace[0], span, "meta", tested_meta)

            assert span["metrics"]["_dd.apm.enabled"] == 0  # if key missing -> APPSEC-55222
            assert span["trace_id"] == trace_id
            assert trace[0]["trace_id"] == trace_id

            # Some tracers use true while others use yes
            assert any(
                ["Datadog-Client-Computed-Stats", trueish] in data["request"]["headers"] for trueish in ["yes", "true"]
            )
            return span["meta"]

        return None

    def _call_endpoint(self, endpoint, trace_id):
        self.r = weblog.get(
            endpoint,
            headers=self._get_test_headers(trace_id),
        )

    def setup_user_login_success_event_generates_asm_event(self):
        trace_id = 1212121212121212111
        self._call_endpoint("/user_login_success_event", trace_id)

    def test_user_login_success_event_generates_asm_event(self):
        trace_id = 1212121212121212111
        meta = self._get_standalone_span_meta(trace_id)
        assert meta is not None
        assert meta["_dd.appsec.events.users.login.success.sdk"] == "true"
        assert "appsec.events.users.login.success.usr.login" in meta

    def setup_user_login_failure_event_generates_asm_event(self):
        trace_id = 1212121212121212122
        self._call_endpoint("/user_login_failure_event", trace_id)

    def test_user_login_failure_event_generates_asm_event(self):
        trace_id = 1212121212121212122
        meta = self._get_standalone_span_meta(trace_id)
        assert meta is not None
        assert meta["_dd.appsec.events.users.login.failure.sdk"] == "true"
        assert "appsec.events.users.login.failure.usr.exists" in meta


@rfc("https://docs.google.com/document/d/18JZdOS5fmnYomRn6OGer0ViS1I6zzT6xl5HMtjDtFn4/edit")
@features.appsec_standalone
@scenarios.appsec_standalone
class Test_UserEventsStandalone_SDK_V2:
    """IAST correctly propagates user events in distributing tracing with DD_APM_TRACING_ENABLED=false."""

    def _get_test_headers(self, trace_id):
        return {
            "x-datadog-trace-id": str(trace_id),
            "x-datadog-parent-id": str(34343434),
            "x-datadog-origin": "rum",
            "x-datadog-sampling-priority": "-1",
            "x-datadog-tags": "_dd.p.other=1",
        }

    def _get_standalone_span_meta(self, trace_id):
        tested_meta = {
            "_dd.p.ts": "02",
        }
        for data, trace, span in interfaces.library.get_spans(request=self.r):
            assert assert_tags(trace[0], span, "meta", tested_meta)

            assert span["metrics"]["_dd.apm.enabled"] == 0  # if key missing -> APPSEC-55222
            assert span["trace_id"] == trace_id
            assert trace[0]["trace_id"] == trace_id

            # Some tracers use true while others use yes
            assert any(
                ["Datadog-Client-Computed-Stats", trueish] in data["request"]["headers"] for trueish in ["yes", "true"]
            )
            return span["meta"]

        return None

    def _call_endpoint(self, endpoint, data, trace_id):
        self.r = weblog.post(endpoint, headers=self._get_test_headers(trace_id), json=data)

    def setup_user_login_success_event_generates_asm_event(self):
        trace_id = 1212121212121212111
        data = {"login": "test_login", "user_id": "test_user_id", "metadata": {"foo": "bar"}}
        self._call_endpoint("/user_login_success_event_v2", data, trace_id)

    def test_user_login_success_event_generates_asm_event(self):
        trace_id = 1212121212121212111
        meta = self._get_standalone_span_meta(trace_id)
        assert meta is not None
        assert meta["_dd.appsec.events.users.login.success.sdk"] == "true"
        assert "appsec.events.users.login.success.usr.login" in meta

    def setup_user_login_failure_event_generates_asm_event(self):
        trace_id = 1212121212121212122
        data = {"login": "test_login", "exists": "true", "metadata": {"foo": "bar"}}
        self._call_endpoint("/user_login_failure_event_v2", data, trace_id)

    def test_user_login_failure_event_generates_asm_event(self):
        trace_id = 1212121212121212122
        meta = self._get_standalone_span_meta(trace_id)
        assert meta is not None
        assert meta["_dd.appsec.events.users.login.failure.sdk"] == "true"
        assert "appsec.events.users.login.failure.usr.exists" in meta
