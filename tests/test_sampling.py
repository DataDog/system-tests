# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from random import randint

from utils import context, BaseTestCase, interfaces, bug, irrelevant, missing_feature, flaky, released


@irrelevant(context.sampling_rate is None, reason="Sampling rates should be set for this test to be meaningful")
@released(php="0.71.0")
class Test_SamplingDecisions(BaseTestCase):
    """Sampling configuration"""

    rid = 0

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    @classmethod
    def next_request_id(cls):
        rid = cls.rid
        cls.rid += 1
        return rid

    @irrelevant(
        context.library in ("nodejs", "php", "dotnet"),
        reason="sampling decision implemented differently in these tracers which isnt't problematic. Cf https://datadoghq.atlassian.net/browse/AIT-374 for more info.",
    )
    @missing_feature(library="cpp", reason="https://github.com/DataDog/dd-opentracing-cpp/issues/173")
    @bug(context.library < "java@0.92.0")
    @flaky(context.library < "python@0.57.0")
    @flaky(context.library >= "java@0.98.0", reason="APMJAVA-743")
    @flaky(
        library="ruby",
        weblog_variant="sinatra14",
        reason="fails randomly for Sinatra on JSON body that dutifully keeps",
    )
    @flaky(
        library="ruby",
        weblog_variant="sinatra20",
        reason="fails randomly for Sinatra on JSON body that dutifully keeps",
    )
    @flaky(
        library="ruby",
        weblog_variant="sinatra21",
        reason="fails randomly for Sinatra on JSON body that dutifully keeps",
    )
    def test_sampling_decision(self):
        """Verify that traces are sampled following the sample rate"""

        # Generate enough traces to have a high chance to catch sampling problems
        for _ in range(30):
            r = self.weblog_get(f"/sample_rate_route/{self.next_request_id()}")

        interfaces.library.assert_sampling_decision_respected(context.sampling_rate)

    @bug(library="python", reason="Sampling decisions are not taken by the tracer APMRP-259")
    @bug(library="ruby", reason="Unknown reason")
    def test_sampling_decision_added(self):
        """Verify that the distributed traces without sampling decisions have a sampling decision added"""

        traces = [{"trace_id": randint(1, 2 ** 64 - 1), "parent_id": randint(1, 2 ** 64 - 1)} for _ in range(20)]

        for trace in traces:
            r = self.weblog_get(
                f"/sample_rate_route/{self.next_request_id()}",
                headers={"x-datadog-trace-id": str(trace["trace_id"]), "x-datadog-parent-id": str(trace["parent_id"])},
            )

        interfaces.library.assert_sampling_decisions_added(traces)

    @bug(library="python", reason="APMRP-259")
    @bug(library="nodejs", reason="APMRP-258")
    @bug(library="ruby", reason="APMRP-258")
    @bug(library="php", reason="APMRP-258")
    def test_sampling_determinism(self):
        """Verify that the way traces are sampled are at least deterministic on trace and span id"""

        traces = [{"trace_id": randint(1, 2 ** 64 - 1), "parent_id": randint(1, 2 ** 64 - 1)} for _ in range(20)]

        for t in traces:
            interfaces.library.uniqueness_exceptions.add_trace_id(t["trace_id"])

        # Send requests with the same trace and parent id twice
        for _ in range(2):
            for trace in traces:
                r = self.weblog_get(
                    f"/sample_rate_route/{self.next_request_id()}",
                    headers={
                        "x-datadog-trace-id": str(trace["trace_id"]),
                        "x-datadog-parent-id": str(trace["parent_id"]),
                    },
                )

        interfaces.library.assert_deterministic_sampling_decisions(traces)
