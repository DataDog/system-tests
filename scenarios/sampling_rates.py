# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from threading import Lock
import time

from utils import BaseTestCase, interfaces, context, bug, not_relevant, missing_feature
from utils.interfaces._core import BaseValidation
from utils.interfaces._library._utils import get_root_spans
from utils.warmups import default_warmup

context.add_warmup(default_warmup)


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
        for trace in data["request"]["content"]["traces"]:
            self.agent_forwarded[int(trace["traceID"])] = trace

    def final_check(self):
        with self.library_sampled_lock:
            sampled_not_fwd = self.library_sampled.keys() - self.agent_forwarded.keys()
        if len(sampled_not_fwd) > 0:
            self.set_failure(
                "Detected traces that were sampled by library, but not submitted to the backed:\n"
                "\n".join(
                    f"\ttraceid {t_id} in library message {self.library_sampled[t_id]['message_number']}"
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
                    f"Message: {data['message_number']}:"
                    "Metric _sampling_priority_v1 should be set on traces that with sampling decision"
                )
                return
            self.sampled_count[sampling_priority == 1] += 1

    def final_check(self):
        trace_count = sum(self.sampled_count.values())
        # 95% confidence interval = 3 * std_dev = 2 * √(n * p (1 - p))
        confidence_interval = 3 * (trace_count * context.sampling_rate * (1.0 - context.sampling_rate)) ** (1 / 2)
        # E = n * p
        expectation = context.sampling_rate * trace_count
        if not (expectation - confidence_interval <= self.sampled_count[True] <= expectation + confidence_interval):
            self.set_failure(
                f"Sampling rate is set to {context.sampling_rate}, expected count of sampled traces {expectation}/{trace_count}."
                f"Actual {self.sampled_count[True]}/{trace_count}={self.sampled_count[True]/trace_count}, "
                f"wich is outside of the confidence interval of +-{confidence_interval}\n"
                "This test is probabilistic in nature and should fail ~5% of the time, you might want to rerun it."
            )
        else:
            self.log_info(
                f"Sampling rate is set to {context.sampling_rate}, expected count of sampled traces {expectation}/{trace_count}."
                f"Actual {self.sampled_count[True]}/{trace_count}={self.sampled_count[True]/trace_count}, "
                f"wich is inside the confidence interval of +-{confidence_interval}"
            )


@missing_feature(library="cpp", reason="https://github.com/DataDog/dd-opentracing-cpp/issues/173")
@not_relevant(context.weblog_variant == "echo-poc", reason="echo isn't instrumented")
@bug(library="golang")
class TestSamplingRates(BaseTestCase):
    TOTAL_REQUESTS = 10_000
    REQ_PER_S = 25

    def test_sampling_rate_is_set(self):
        """Should fail if the test is misconfigured"""
        if context.sampling_rate is None:
            raise Exception("Sampling rate should be set on tracer with an env var for this scenario to be meaningful")

    def test_sampling_rates(self):
        """Tests that the rate at which traces are sampled is the actual sample rate"""
        paths = []
        last_sleep = time.time()
        for i in range(self.TOTAL_REQUESTS):
            if i != 0 and i % self.REQ_PER_S == 0:
                time.sleep(max(0, 1 - (time.time() - last_sleep)))
                last_sleep = time.time()
            p = f"/sample_rate_route/{i}"
            paths.append(p)
            r = self.weblog_get(p)
            assert r.status_code == 200
        interfaces.library.assert_all_traces_requests_forwarded(paths)
        interfaces.library.append_validation(LibrarySamplingRateValidation())
        interfaces.agent.append_validation(AgentSampledFwdValidation())
