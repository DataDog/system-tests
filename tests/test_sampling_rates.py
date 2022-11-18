# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from threading import Lock
import time
from random import randint

from utils import BaseTestCase, interfaces, context, missing_feature, released, bug, irrelevant, flaky, scenario
from utils.interfaces._core import BaseValidation
from utils.interfaces._library._utils import get_root_spans

AUTO_KEEP = 1
USER_KEEP = 2


class AgentSampledFwdValidation(BaseValidation):
    is_success_on_expiry = True
    path_filters = ["/api/v0.2/traces"]

    def __init__(self, request=None):
        super().__init__(request=request)
        self.library_sampled = {}
        self.agent_forwarded = {}
        self.library_sampled_lock = Lock()

    def add_library_sampled_trace(self, root_span):
        with self.library_sampled_lock:
            if root_span["trace_id"] in self.library_sampled:
                raise Exception("A trace was added twice to the agent sampling validation")
            self.library_sampled[root_span["trace_id"]] = root_span

    def check(self, data):
        if "tracerPayloads" not in data["request"]["content"]:
            self.set_failure("Trace property is missing in agent payload")
        else:
            for payload in data["request"]["content"]["tracerPayloads"]:
                for trace in payload["chunks"]:
                    for span in trace["spans"]:
                        self.agent_forwarded[int(span["traceID"])] = trace

    def final_check(self):
        with self.library_sampled_lock:
            sampled_not_fwd = self.library_sampled.keys() - self.agent_forwarded.keys()
        if len(sampled_not_fwd) > 0:
            self.set_failure(
                "Detected traces that were sampled by library, but not submitted to the backend:\n"
                "\n".join(
                    f"\ttraceid {t_id} in library message {self.library_sampled[t_id]['log_filename']}"
                    for t_id in sampled_not_fwd
                )
            )
            return
        self.log_info(
            f"Forwarded {len(self.agent_forwarded)} to the backend, from traces sampled {len(self.library_sampled)}"
        )


class LibrarySamplingRateValidation(BaseValidation):
    is_success_on_expiry = True
    path_filters = ["/v0.4/traces"]

    def __init__(self, request=None):
        super().__init__(request=request)
        self.sampled_count = {True: 0, False: 0}

    def check(self, data):
        for root_span in get_root_spans(data["request"]["content"]):
            sampling_priority = root_span["metrics"].get("_sampling_priority_v1")
            if sampling_priority is None:
                self.set_failure(
                    f"Message: {data['log_filename']}:"
                    "Metric _sampling_priority_v1 should be set on traces that with sampling decision"
                )
                return
            self.sampled_count[sampling_priority in (USER_KEEP, AUTO_KEEP)] += 1

    def final_check(self):
        trace_count = sum(self.sampled_count.values())
        # 95% confidence interval = 3 * std_dev = 2 * √(n * p (1 - p))
        confidence_interval = 3 * (trace_count * context.sampling_rate * (1.0 - context.sampling_rate)) ** (1 / 2)
        # E = n * p
        expectation = context.sampling_rate * trace_count
        if not expectation - confidence_interval <= self.sampled_count[True] <= expectation + confidence_interval:
            self.set_failure(
                f"Sampling rate is set to {context.sampling_rate}, "
                f"expected count of sampled traces {expectation}/{trace_count}."
                f"Actual {self.sampled_count[True]}/{trace_count}={self.sampled_count[True]/trace_count}, "
                f"wich is outside of the confidence interval of +-{confidence_interval}\n"
                "This test is probabilistic in nature and should fail ~5% of the time, you might want to rerun it."
            )
        else:
            self.log_info(
                f"Sampling rate is set to {context.sampling_rate}, "
                f"expected count of sampled traces {expectation}/{trace_count}."
                f"Actual {self.sampled_count[True]}/{trace_count}={self.sampled_count[True]/trace_count}, "
                f"wich is inside the confidence interval of +-{confidence_interval}"
            )


@missing_feature(library="cpp", reason="https://github.com/DataDog/dd-opentracing-cpp/issues/173")
@bug(context.library >= "golang@1.35.0" and context.library < "golang@1.36.2")
@bug(context.agent_version < "7.33.0", reason="Before this version, tracerPayloads was named traces")
@scenario("SAMPLING")
class Test_SamplingRates(BaseTestCase):
    """Rate at which traces are sampled is the actual sample rate"""

    TOTAL_REQUESTS = 10_000
    REQ_PER_S = 25

    def test_sampling_rate_is_set(self):
        """Should fail if the test is misconfigured"""
        if context.sampling_rate is None:
            raise Exception("Sampling rate should be set on tracer with an env var for this scenario to be meaningful")

    @bug(library="python", reason="When stats are activated, all traces are emitted")
    def test_sampling_rates(self):
        """Basic test"""
        paths = []
        last_sleep = time.time()
        for i in range(self.TOTAL_REQUESTS):
            if i != 0 and i % self.REQ_PER_S == 0:
                time.sleep(max(0, 1 - (time.time() - last_sleep)))
                last_sleep = time.time()
            p = f"/sample_rate_route/{i}"
            paths.append(p)
            self.weblog_get(p)

        interfaces.library.assert_all_traces_requests_forwarded(paths)
        interfaces.library.append_validation(LibrarySamplingRateValidation())
        interfaces.agent.append_validation(AgentSampledFwdValidation())


@released(php="0.71.0")
@scenario("SAMPLING")
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
        reason=(
            "sampling decision implemented differently in these tracers which isnt't problematic. "
            "Cf https://datadoghq.atlassian.net/browse/AIT-374 for more info."
        ),
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
            self.weblog_get(f"/sample_rate_route/{self.next_request_id()}")

        interfaces.library.assert_sampling_decision_respected(context.sampling_rate)

    @bug(library="python", reason="Sampling decisions are not taken by the tracer APMRP-259")
    @bug(library="ruby", reason="Unknown reason")
    def test_sampling_decision_added(self):
        """Verify that the distributed traces without sampling decisions have a sampling decision added"""

        traces = [{"trace_id": randint(1, 2 ** 64 - 1), "parent_id": randint(1, 2 ** 64 - 1)} for _ in range(20)]

        for trace in traces:
            self.weblog_get(
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
                self.weblog_get(
                    f"/sample_rate_route/{self.next_request_id()}",
                    headers={
                        "x-datadog-trace-id": str(trace["trace_id"]),
                        "x-datadog-parent-id": str(trace["parent_id"]),
                    },
                )

        interfaces.library.assert_deterministic_sampling_decisions(traces)
