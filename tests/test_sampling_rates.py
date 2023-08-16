# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from collections import defaultdict
from random import randint, seed

from utils import weblog, interfaces, context, missing_feature, released, bug, irrelevant, flaky, scenarios
from utils.tools import logger


USER_REJECT = -1
AUTO_REJECT = 0
AUTO_KEEP = 1
USER_KEEP = 2


def sample_from_rate(sampling_rate, trace_id):
    """Algorithm described in the priority sampling RFC
    https://github.com/DataDog/architecture/blob/master/rfcs/apm/integrations/priority-sampling/rfc.md"""
    MAX_TRACE_ID = 2 ** 64
    KNUTH_FACTOR = 1111111111111111111

    return ((trace_id * KNUTH_FACTOR) % MAX_TRACE_ID) <= (sampling_rate * MAX_TRACE_ID)


def _spans_with_parent(traces, parent_ids):
    if not isinstance(traces, list):
        logger.error("Traces should be an array")
        yield from []  # do notfail here, it's schema's job
    else:
        for trace in traces:
            for span in trace:
                if span.get("parent_id") in parent_ids:
                    yield span


@missing_feature(library="cpp", reason="https://github.com/DataDog/dd-opentracing-cpp/issues/173")
@bug(context.library >= "golang@1.35.0" and context.library < "golang@1.36.2")
@bug(context.agent_version < "7.33.0", reason="Before this version, tracerPayloads was named traces")
@scenarios.sampling
class Test_SamplingRates:
    """Rate at which traces are sampled is the actual sample rate"""

    TOTAL_REQUESTS = 2_000

    def setup_sampling_rates(self):
        self.paths = []
        for i in range(self.TOTAL_REQUESTS):
            p = f"/sample_rate_route/{i}"
            self.paths.append(p)
            weblog.get(p)

    @bug(library="python", reason="When stats are activated, all traces are emitted")
    @bug(context.library > "nodejs@3.14.1", reason="_sampling_priority_v1 is missing")
    @flaky(context.weblog_variant == "spring-boot-3-native", reason="Needs investigation")
    @flaky(library="golang", reason="Needs investigation")
    @flaky(library="ruby", reason="Needs investigation")
    def test_sampling_rates(self):
        """Basic test"""
        interfaces.library.assert_all_traces_requests_forwarded(self.paths)

        # test sampling
        sampled_count = {True: 0, False: 0}

        for data, root_span in interfaces.library.get_root_spans():
            metrics = root_span["metrics"]
            assert "_sampling_priority_v1" in metrics, f"_sampling_priority_v1 is missing in {data['log_filename']}"
            sampled_count[metrics["_sampling_priority_v1"] in (USER_KEEP, AUTO_KEEP)] += 1

        trace_count = sum(sampled_count.values())
        # 95% confidence interval = 4 * std_dev = 4 * √(n * p (1 - p))
        confidence_interval = 4 * (
            trace_count * context.tracer_sampling_rate * (1.0 - context.tracer_sampling_rate)
        ) ** (1 / 2)
        # E = n * p
        expectation = context.tracer_sampling_rate * trace_count
        if not expectation - confidence_interval <= sampled_count[True] <= expectation + confidence_interval:
            raise ValueError(
                f"Sampling rate is set to {context.tracer_sampling_rate}, "
                f"expected count of sampled traces {expectation}/{trace_count}."
                f"Actual {sampled_count[True]}/{trace_count}={sampled_count[True]/trace_count}, "
                f"wich is outside of the confidence interval of +-{confidence_interval}\n"
                "This test is probabilistic in nature and should fail ~5% of the time, you might want to rerun it."
            )

        # Test that all traces sent by the tracer is sent to the agent"""
        trace_ids = set()

        for data, span in interfaces.library.get_root_spans():
            metrics = span["metrics"]
            if metrics["_sampling_priority_v1"] not in (USER_REJECT, AUTO_REJECT):
                trace_ids.add(span["trace_id"])

        for _, span in interfaces.agent.get_spans():
            trace_id = int(span["traceID"])
            if trace_id in trace_ids:
                trace_ids.remove(trace_id)

        assert len(trace_ids) == 0, f"Some traces has not been sent by the agent: {trace_ids}"


@released(php="0.71.0")
@scenarios.sampling
class Test_SamplingDecisions:
    """Sampling configuration"""

    rid = 0

    @classmethod
    def next_request_id(cls):
        rid = cls.rid
        cls.rid += 1
        return rid

    def setup_sampling_decision(self):
        # Generate enough traces to have a high chance to catch sampling problems
        for _ in range(30):
            weblog.get(f"/sample_rate_route/{self.next_request_id()}")

    @irrelevant(context.library in ("nodejs", "php", "dotnet"), reason="AIT-374")
    @missing_feature(library="cpp", reason="https://github.com/DataDog/dd-opentracing-cpp/issues/173")
    @bug(context.library < "java@0.92.0")
    @flaky(context.library < "python@0.57.0")
    @flaky(context.library >= "java@0.98.0", reason="APMJAVA-743")
    @flaky(
        context.library == "ruby" and context.weblog_variant in ("sinatra14", "sinatra20", "sinatra21", "uds-sinatra"),
        reason="fails randomly for Sinatra on JSON body that dutifully keeps",
    )
    @bug(context.library >= "python@1.11.0rc2.dev8", reason="Under investigation")
    @bug(library="golang", reason="Need investigation")
    @missing_feature(library="ruby", reason="Route /sample_rate_route not implemented")
    def test_sampling_decision(self):
        """Verify that traces are sampled following the sample rate"""

        def validator(data, root_span):
            sampling_priority = root_span["metrics"].get("_sampling_priority_v1")
            if sampling_priority is None:
                raise ValueError(
                    f"Message: {data['log_filename']}:"
                    "Metric _sampling_priority_v1 should be set on traces that with sampling decision"
                )

            sampling_decision = sampling_priority > 0
            expected_decision = sample_from_rate(context.tracer_sampling_rate, root_span["trace_id"])
            if sampling_decision != expected_decision:
                raise ValueError(
                    f"Trace id {root_span['trace_id']}, sampling priority {sampling_priority}, "
                    f"sampling decision {sampling_decision} differs from the expected {expected_decision}"
                )

        for data, span in interfaces.library.get_root_spans():
            validator(data, span)

    def setup_sampling_decision_added(self):
        self.traces = [{"trace_id": randint(1, 2 ** 64 - 1), "parent_id": randint(1, 2 ** 64 - 1)} for _ in range(20)]

        for trace in self.traces:
            weblog.get(
                f"/sample_rate_route/{self.next_request_id()}",
                headers={"x-datadog-trace-id": str(trace["trace_id"]), "x-datadog-parent-id": str(trace["parent_id"]),},
            )

    @bug(library="python", reason="Sampling decisions are not taken by the tracer APMRP-259")
    @bug(context.library > "nodejs@3.14.1", reason="_sampling_priority_v1 is missing")
    @missing_feature(library="ruby", reason="Route /sample_rate_route not implemented")
    def test_sampling_decision_added(self):
        """Verify that the distributed traces without sampling decisions have a sampling decision added"""

        traces = {trace["parent_id"]: trace for trace in self.traces}
        spans = []

        def validator(data):
            for span in _spans_with_parent(data["request"]["content"], traces.keys()):
                expected_trace_id = traces[span["parent_id"]]["trace_id"]
                spans.append(span)

                assert span["trace_id"] == expected_trace_id, (
                    f"Message: {data['log_filename']}: If parent_id matches, "
                    f"trace_id should match too expected trace_id {expected_trace_id} "
                    f"span trace_id : {span['trace_id']}, span parent_id : {span['parent_id']}",
                )

                sampling_priority = span["metrics"].get("_sampling_priority_v1")

                assert sampling_priority is not None, (
                    f"Message: {data['log_filename']}: sampling priority should be set on span {span['span_id']}",
                )

        interfaces.library.validate(validator, path_filters=["/v0.4/traces", "/v0.5/traces"], success_by_default=True)

        if len(spans) != len(traces):
            raise ValueError("Didn't see all requests")

    def setup_sampling_determinism(self):
        seed(0)  # stay deterministic

        self.traces_determinism = [
            {"trace_id": randint(1, 2 ** 64 - 1), "parent_id": randint(1, 2 ** 64 - 1)} for _ in range(20)
        ]

        # Send requests with the same trace and parent id twice
        for _ in range(2):
            for trace in self.traces_determinism:
                weblog.get(
                    f"/sample_rate_route/{self.next_request_id()}",
                    headers={
                        "x-datadog-trace-id": str(trace["trace_id"]),
                        "x-datadog-parent-id": str(trace["parent_id"]),
                    },
                )

    @bug(library="python", reason="APMRP-259")
    @bug(library="nodejs", reason="APMRP-258")
    @bug(library="ruby", reason="APMRP-258")
    @bug(library="php", reason="APMRP-258")
    @flaky(library="cpp")
    @flaky(library="golang")
    def test_sampling_determinism(self):
        """Verify that the way traces are sampled are at least deterministic on trace and span id"""

        traces = {trace["parent_id"]: trace for trace in self.traces_determinism}
        sampling_decisions_per_trace_id = defaultdict(list)

        def validator(data):
            for span in _spans_with_parent(data["request"]["content"], traces.keys()):
                expected_trace_id = traces[(span["parent_id"])]["trace_id"]
                sampling_priority = span["metrics"].get("_sampling_priority_v1")
                sampling_decisions_per_trace_id[span["trace_id"]].append(sampling_priority)

                assert span["trace_id"] == expected_trace_id, (
                    f"Message: {data['log_filename']}: If parent_id matches, "
                    f"trace_id should match too expected trace_id {expected_trace_id} "
                    f"span trace_id : {span['trace_id']}, span parent_id : {span['parent_id']}",
                )

                assert (
                    sampling_priority is not None
                ), f"Message: {data['log_filename']}: sampling priority should be set"

        interfaces.library.validate(validator, path_filters=["/v0.4/traces", "/v0.5/traces"], success_by_default=True)

        for trace_id, decisions in sampling_decisions_per_trace_id.items():
            if len(decisions) < 2:
                continue

            if not all((d == decisions[0] for d in decisions)):
                raise ValueError(f"Sampling decisions are not deterministic for trace_id {trace_id}: {decisions}")
