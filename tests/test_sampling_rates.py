# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import time
from random import randint

from utils import weblog, interfaces, context, missing_feature, released, bug, irrelevant, flaky, scenarios

USER_REJECT = -1
AUTO_REJECT = 0
AUTO_KEEP = 1
USER_KEEP = 2


@missing_feature(library="cpp", reason="https://github.com/DataDog/dd-opentracing-cpp/issues/173")
@bug(context.library >= "golang@1.35.0" and context.library < "golang@1.36.2")
@bug(context.agent_version < "7.33.0", reason="Before this version, tracerPayloads was named traces")
@scenarios.sampling
class Test_SamplingRates:
    """Rate at which traces are sampled is the actual sample rate"""

    TOTAL_REQUESTS = 10_000
    REQ_PER_S = 25

    def test_sampling_rate_is_set(self):
        """Should fail if the test is misconfigured"""
        if context.tracer_sampling_rate is None:
            raise Exception("Sampling rate should be set on tracer with an env var for this scenario to be meaningful")

    def setup_sampling_rates(self):
        self.paths = []
        last_sleep = time.time()
        for i in range(self.TOTAL_REQUESTS):
            if i != 0 and i % self.REQ_PER_S == 0:
                time.sleep(max(0, 1 - (time.time() - last_sleep)))
                last_sleep = time.time()
            p = f"/sample_rate_route/{i}"
            self.paths.append(p)
            weblog.get(p)

    @bug(library="python", reason="When stats are activated, all traces are emitted")
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
        # 95% confidence interval = 3 * std_dev = 2 * √(n * p (1 - p))
        confidence_interval = 3 * (
            trace_count * context.tracer_sampling_rate * (1.0 - context.tracer_sampling_rate)
        ) ** (1 / 2)
        # E = n * p
        expectation = context.tracer_sampling_rate * trace_count
        if not expectation - confidence_interval <= sampled_count[True] <= expectation + confidence_interval:
            raise Exception(
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
    def test_sampling_decision(self):
        """Verify that traces are sampled following the sample rate"""

        interfaces.library.assert_sampling_decision_respected(context.tracer_sampling_rate)

    def setup_sampling_decision_added(self):

        self.traces = [{"trace_id": randint(1, 2 ** 64 - 1), "parent_id": randint(1, 2 ** 64 - 1)} for _ in range(20)]

        for trace in self.traces:
            weblog.get(
                f"/sample_rate_route/{self.next_request_id()}",
                headers={"x-datadog-trace-id": str(trace["trace_id"]), "x-datadog-parent-id": str(trace["parent_id"]),},
            )

    @bug(library="python", reason="Sampling decisions are not taken by the tracer APMRP-259")
    @bug(library="ruby", reason="Unknown reason")
    def test_sampling_decision_added(self):
        """Verify that the distributed traces without sampling decisions have a sampling decision added"""
        interfaces.library.assert_sampling_decisions_added(self.traces)

    def setup_sampling_determinism(self):
        self.traces_determinism = [
            {"trace_id": randint(1, 2 ** 64 - 1), "parent_id": randint(1, 2 ** 64 - 1)} for _ in range(20)
        ]

        for t in self.traces_determinism:
            interfaces.library.uniqueness_exceptions.add_trace_id(t["trace_id"])

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
    def test_sampling_determinism(self):
        """Verify that the way traces are sampled are at least deterministic on trace and span id"""
        interfaces.library.assert_deterministic_sampling_decisions(self.traces_determinism)
