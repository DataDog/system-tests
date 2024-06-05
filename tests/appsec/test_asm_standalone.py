from utils import weblog, interfaces, scenarios, features
from utils._context.header_tag_vars import *


@scenarios.appsec_standalone
class Test_AppSecPropagation:
    """APM correctly propagates AppSec events in distributing tracing."""

    def setup_trace_no_upstream_appsec_propagation_no_attack_is_dropped(self):
        trace_id = 1212121212121212121
        parent_id = 34343434
        self.r = weblog.get(
            "/waf/",
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
                "x-datadog-origin": "rum",
                "x-datadog-tags": "_dd.p.other=1",
            },
        )

    def test_trace_no_upstream_appsec_propagation_no_attack_is_dropped(self):
        for data, _, span in interfaces.library.get_spans(request=self.r):
            assert span["metrics"]["_sampling_priority_v1"] == -1
            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert "_dd.p.appsec" not in span["meta"]

            # Some tracers use true while others use yes
            assert any(
                [
                    "Datadog-Client-Computed-Stats",
                    trueish,
                ]
                in data["request"]["headers"]
                for trueish in ["yes", "true"]
            )

    def setup_trace_no_upstream_appsec_propagation_with_attack_is_kept(self):
        trace_id = 1212121212121212121
        parent_id = 34343434
        self.r = weblog.get(
            "/waf/",
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
                "x-datadog-origin": "rum",
                "x-datadog-tags": "_dd.p.other=1",
                "User-Agent": "Arachni/v1",
            },
        )

    def test_trace_no_upstream_appsec_propagation_with_attack_is_kept(self):
        for data, _, span in interfaces.library.get_spans(request=self.r):
            assert span["metrics"]["_sampling_priority_v1"] == 2
            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert span["meta"]["_dd.p.appsec"] == "1"

            # Some tracers use true while others use yes
            assert any(
                [
                    "Datadog-Client-Computed-Stats",
                    trueish,
                ]
                in data["request"]["headers"]
                for trueish in ["yes", "true"]
            )

    def setup_trace_upstream_appsec_propagation_no_attack_is_propagated(self):
        trace_id = 1212121212121212121
        parent_id = 34343434
        self.r = weblog.get(
            "/waf/",
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
                "x-datadog-origin": "rum",
                "x-datadog-sampling-priority": "2",
                "x-datadog-tags": "_dd.p.appsec=1",
            },
        )

    def test_trace_upstream_appsec_propagation_no_attack_is_propagated(self):
        for data, _, span in interfaces.library.get_spans(request=self.r):
            assert span["metrics"]["_sampling_priority_v1"] == 2
            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert span["meta"]["_dd.p.appsec"] == "1"

            # Some tracers use true while others use yes
            assert any(
                [
                    "Datadog-Client-Computed-Stats",
                    trueish,
                ]
                in data["request"]["headers"]
                for trueish in ["yes", "true"]
            )

    def setup_trace_any_upstream_propagation_with_attack_raises_priority(self):
        trace_id = 1212121212121212121
        parent_id = 34343434
        self.r = weblog.get(
            "/waf/",
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
                "x-datadog-origin": "rum",
                "x-datadog-sampling-priority": "1",
                "User-Agent": "Arachni/v1",
            },
        )

    def test_trace_any_upstream_propagation_with_attack_raises_priority(self):
        for data, _, span in interfaces.library.get_spans(request=self.r):
            assert span["metrics"]["_sampling_priority_v1"] == 2
            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert span["meta"]["_dd.p.appsec"] == "1"

            # Some tracers use true while others use yes
            assert any(
                [
                    "Datadog-Client-Computed-Stats",
                    trueish,
                ]
                in data["request"]["headers"]
                for trueish in ["yes", "true"]
            )

    def setup_trace_drop_upstream_propagation_with_attack_raises_priority(self):
        trace_id = 1212121212121212121
        parent_id = 34343434
        self.r = weblog.get(
            "/waf/",
            headers={
                "x-datadog-trace-id": str(trace_id),
                "x-datadog-parent-id": str(parent_id),
                "x-datadog-origin": "rum",
                "x-datadog-sampling-priority": "-1",
                "User-Agent": "Arachni/v1",
            },
        )

    def test_trace_drop_upstream_propagation_with_attack_raises_priority(self):
        for data, _, span in interfaces.library.get_spans(request=self.r):
            assert span["metrics"]["_sampling_priority_v1"] == 2
            assert span["metrics"]["_dd.apm.enabled"] == 0
            assert span["meta"]["_dd.p.appsec"] == "1"

            # Some tracers use true while others use yes
            assert any(
                [
                    "Datadog-Client-Computed-Stats",
                    trueish,
                ]
                in data["request"]["headers"]
                for trueish in ["yes", "true"]
            )
