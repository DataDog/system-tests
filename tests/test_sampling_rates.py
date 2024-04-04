# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from collections import defaultdict
import csv
from random import randint, seed

from utils import weblog, interfaces, context, missing_feature, bug, irrelevant, flaky, scenarios, features
from utils.tools import logger


def priority_should_be_kept(sampling_priority):
    """ Returns if a given sampling priority means its trace has to be kept.

    See https://datadoghq.atlassian.net/wiki/spaces/APM/pages/2564915820/Trace+Ingestion+Mechanisms
    """
    AUTO_KEEP = 1
    USER_KEEP = 2

    return sampling_priority in (AUTO_KEEP, USER_KEEP)


def trace_should_be_kept(sampling_rate, trace_id):
    """Given a trace_id and a sampling rate, returns if a trace should be kept.
    
    Reference algorithm described in the priority sampling RFC
    https://github.com/DataDog/architecture/blob/master/rfcs/apm/integrations/priority-sampling/rfc.md
    """
    MODULO = 2 ** 64
    KNUTH_FACTOR = 1111111111111111111

    return ((trace_id * KNUTH_FACTOR) % MODULO) <= (sampling_rate * MODULO)


def _spans_with_parent(traces, parent_ids):
    if not isinstance(traces, list):
        logger.error("Traces should be an array")
        yield from []  # do notfail here, it's schema's job
    else:
        for trace in traces:
            for span in trace:
                if span.get("parent_id") in parent_ids:
                    yield span


@bug(context.library >= "golang@1.35.0" and context.library < "golang@1.36.2")
@bug(context.agent_version < "7.33.0", reason="Before this version, tracerPayloads was named traces")
@scenarios.sampling
@features.twl_customer_controls_ingestion_dd_trace_sampling_rules
@features.ensure_that_sampling_is_consistent_across_languages
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
    @bug(
        context.library > "nodejs@3.14.1" and context.library < "nodejs@4.8.0",
        reason="_sampling_priority_v1 is missing",
    )
    @bug(library="nodejs", reason="Unexpected amount of sampled traces")
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
            sampled_count[priority_should_be_kept(metrics["_sampling_priority_v1"])] += 1

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
                f"which is outside of the confidence interval of +-{confidence_interval}\n"
                "This test is probabilistic in nature and should fail ~5% of the time, you might want to rerun it."
            )

        # Test that all traces sent by the tracer are sent to the agent
        trace_ids = set()

        for data, span in interfaces.library.get_root_spans():
            metrics = span["metrics"]
            if priority_should_be_kept(metrics["_sampling_priority_v1"]):
                trace_ids.add(span["trace_id"])

        for _, span in interfaces.agent.get_spans():
            trace_id = int(span["traceID"])
            if trace_id in trace_ids:
                trace_ids.remove(trace_id)

        assert len(trace_ids) == 0, f"Some traces have not been sent by the agent: {trace_ids}"


@scenarios.sampling
@features.ensure_that_sampling_is_consistent_across_languages
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
    def test_sampling_decision(self):
        """Verify that traces are sampled following the sample rate"""

        def validator(data, root_span):
            sampling_priority = root_span["metrics"].get("_sampling_priority_v1")
            if sampling_priority is None:
                raise ValueError(
                    f"Message: {data['log_filename']}:"
                    "Metric _sampling_priority_v1 should be set on traces that with sampling decision"
                )

            sampling_decision = priority_should_be_kept(sampling_priority)
            expected_decision = trace_should_be_kept(context.tracer_sampling_rate, root_span["trace_id"])
            if sampling_decision != expected_decision:
                raise ValueError(
                    f"Trace id {root_span['trace_id']}, sampling priority {sampling_priority}, "
                    f"sampling decision {sampling_decision} differs from the expected {expected_decision}"
                )

        for data, span in interfaces.library.get_root_spans():
            validator(data, span)

    def setup_sampling_decision_added(self):
        seed(1)  # stay deterministic

        self.traces = [{"trace_id": randint(1, 2 ** 64 - 1), "parent_id": randint(1, 2 ** 64 - 1)} for _ in range(20)]

        for trace in self.traces:
            weblog.get(
                f"/sample_rate_route/{self.next_request_id()}",
                headers={"x-datadog-trace-id": str(trace["trace_id"]), "x-datadog-parent-id": str(trace["parent_id"]),},
            )

    @bug(library="python", reason="Sampling decisions are not taken by the tracer APMRP-259")
    @bug(
        context.library > "nodejs@3.14.1" and context.library < "nodejs@4.8.0",
        reason="_sampling_priority_v1 is missing",
    )
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
            raise ValueError(f"Didn't see all requests, expecting {len(traces)}, saw {len(spans)}")

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

    def _load_csv_sampling_decisions(self):
        cases = []
        with open("tests/fixtures/sampling_rates.csv", newline="", encoding="utf-8") as csv_file:
            r = csv.reader(csv_file)
            for row in r:
                trace_id, sampling_rate, sampling_priority = (int(row[0]), float(row[1]), int(row[2]))
                if sampling_rate != context.tracer_sampling_rate:
                    # This test can only run on an app with a static sampling rate (default: 0.5).
                    logger.warning(
                        "skipped fixture trace_id:%s because of sampling rate different from %s",
                        trace_id,
                        sampling_rate,
                    )
                    continue
                # Check that the input .csv is valid according to this test's implementation of trace_should_be_kept.
                assert priority_should_be_kept(sampling_priority) is trace_should_be_kept(sampling_rate, trace_id)
                cases.append((trace_id, sampling_rate, sampling_priority))
        return cases

    def setup_sample_rate_function(self):
        self.requests_expected_decision = []

        for trace_id, _, sampling_priority in self._load_csv_sampling_decisions():
            sampling_decision = priority_should_be_kept(sampling_priority)
            # The value of the parent_id doesn't matter.
            parent_id = trace_id
            # Each request hits a different URL to help troubleshooting, it isn't required for the test.
            req = weblog.get(
                f"/sample_rate_route/{self.next_request_id()}",
                headers={"x-datadog-trace-id": str(trace_id), "x-datadog-parent-id": str(parent_id),},
            )
            # Map request results so that the test can validate them.
            self.requests_expected_decision.append((req, sampling_decision))

    @bug(library="python", reason="APMRP-259")
    @bug(library="nodejs", reason="APMRP-258")
    @bug(library="php", reason="APMRP-258")
    @bug(library="cpp", reason="APMRP-258")
    @bug(context.library < "dotnet@2.37.0", reason="APMRP-258")
    def test_sample_rate_function(self):
        """Tests the sampling decision follows the one from the sampling function specification."""

        for req, sampling_decision in self.requests_expected_decision:
            # Ensure the request succeeded, any failure would make the test incorrect.
            assert req.status_code == 200, "Call to /sample_rate_route/:i failed"

            for data, _, span in interfaces.library.get_spans(request=req):
                # Validate the sampling decision
                trace_id = span["trace_id"]
                sampling_priority = span["metrics"].get("_sampling_priority_v1")
                logger.info(f"Tring to validate trace_id:{trace_id} from {data['log_filename']}")
                logger.info(f"Sampling priority: {sampling_priority}")
                assert sampling_priority is not None, "Root span has no sampling priority attached"
                assert priority_should_be_kept(sampling_priority) is sampling_decision
                break
            else:
                raise ValueError(f"Did not receive spans for req:{req.request}")
