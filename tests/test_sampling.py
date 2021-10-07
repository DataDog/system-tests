from random import randint

from utils import context, BaseTestCase, interfaces, skipif


@skipif(
    context.sampling_rate is None, reason="not relevant: Sampling rates should be set for this test to be meaningful"
)
@skipif(
    context.library == "golang" and context.weblog_variant == "echo-poc",
    reason="Not relevant: echo is not instrumented",
)
class Test_SamplingDecisions(BaseTestCase):
    rid = 0

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    @classmethod
    def next_request_id(cls):
        rid = cls.rid
        cls.rid += 1
        return rid

    @skipif(
        context.library in ("nodejs", "php", "dotnet"),
        reason="todo tracer: sampling decision implemented differently in these tracers",
    )
    @skipif(
        context.library == "cpp", reason="missing feature: https://github.com/DataDog/dd-opentracing-cpp/issues/173",
    )
    @skipif(context.library == "java", reason="known bug?")
    def test_sampling_decision(self):
        """Verify that traces are sampled following the sample rate"""

        # Generate enough traces to have a high chance to catch sampling problems
        for _ in range(30):
            r = self.weblog_get(f"/sample_rate_route/{self.next_request_id()}")
            assert r.status_code == 200
        interfaces.library.assert_sampling_decision_respected(context.sampling_rate)

    @skipif(
        context.library in ("golang", "python"),
        reason="known bug: Sampling decisions are not taken by the tracer APMRP-259",
    )
    def test_sampling_decision_added(self):
        """Verify that the distributed traces without sampling decisions have a sampling decision added"""

        traces = [{"trace_id": randint(1, 2 ** 64 - 1), "parent_id": randint(1, 2 ** 64 - 1)} for _ in range(20)]

        for trace in traces:
            r = self.weblog_get(
                f"/sample_rate_route/{self.next_request_id()}",
                headers={"x-datadog-trace-id": str(trace["trace_id"]), "x-datadog-parent-id": str(trace["parent_id"])},
            )
            assert r.status_code == 200
        interfaces.library.assert_sampling_decisions_added(traces)

    @skipif(
        context.library in ("nodejs", "ruby", "php"),
        reason="known bug: Sampling decision is non deterministic https://datadoghq.atlassian.net/browse/APMRP-258",
    )
    @skipif(
        context.library in ("golang", "python"),
        reason="known bug: Sampling decisions are not taken by the tracer APMRP-259",
    )
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
                assert r.status_code == 200
        interfaces.library.assert_deterministic_sampling_decisions(traces)
