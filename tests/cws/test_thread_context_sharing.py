# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json
import uuid

from utils import features, interfaces, scenarios, weblog

from .utils import CWS_EVENTS_PATH, cws_event_mentioning, cws_self_test_succeeded


@features.not_reported
@scenarios.thread_context_sharing
class Test_ThreadContextSharing:
    """A tracer that shares the trace_id/span_id of the span active on a thread with system-probe
    lets CWS (Cloud Workload Security) correlate a security event with the request that triggered it.

    See docs/understand/weblogs/end-to-end_weblog.md, "GET /security/thread_context_sharing".
    """

    def setup_open_file_carries_trace_context(self):
        # CWS drops events generated before its pipeline is live, so hold the request back
        # until the agent's self test reports success.
        self.cws_ready = interfaces.agent.wait_for(cws_self_test_succeeded, timeout=50)

        self.canary_path = f"/tmp/system-tests-thread-context-sharing-{uuid.uuid4()}"
        self.response = weblog.get("/security/thread_context_sharing", params={"path": self.canary_path})

        # unique per request so we can pick out this test's own event among concurrent tests
        interfaces.agent.wait_for(
            lambda data: cws_event_mentioning(data, self.canary_path) is not None,
            timeout=35,
        )

    def test_open_file_carries_trace_context(self):
        assert self.cws_ready, "CWS never reported a successful self test, so no security event can be expected"
        assert self.response.status_code == 200

        body = json.loads(self.response.text)
        # CWS serializes trace_id as unpadded lowercase hex, and span_id as decimal
        expected_trace_id = format(int(body["trace_id"]), "x")
        expected_span_id = str(body["span_id"])

        event = None
        for data in interfaces.agent.get_data(CWS_EVENTS_PATH):
            event = cws_event_mentioning(data, self.canary_path)
            if event is not None:
                break

        assert event is not None, f"No CWS event observed for {self.canary_path} within the timeout"

        dd = event.get("dd") or {}
        trace_id, span_id = dd.get("trace_id"), dd.get("span_id")
        assert trace_id == expected_trace_id, f"Expected dd.trace_id={expected_trace_id}, got {trace_id}"
        assert span_id == expected_span_id, f"Expected dd.span_id={expected_span_id}, got {span_id}"
