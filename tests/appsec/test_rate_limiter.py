# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import datetime
import pytest
from utils import weblog, context, coverage, interfaces, released, rfc, bug, scenarios, missing_feature

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@rfc("https://docs.google.com/document/d/1X64XQOk3N-aS_F0bJuZLkUiJqlYneDxo_b8WnkfFy_0")
@released(dotnet="2.6.0", nodejs="2.0.0")
@bug(
    context.library in ("nodejs@3.2.0", "nodejs@2.15.0"), weblog_variant="express4", reason="APPSEC-5427",
)
@coverage.basic
@scenarios.appsec_rate_limiter
@missing_feature(context.weblog_variant == "spring-boot-native", reason="GraalVM. Tracing support only")
@missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
class Test_Main:
    """Basic tests for rate limiter"""

    # TODO: a scenario with DD_TRACE_SAMPLE_RATE set to something
    # as sampling mechnism is very different across agent, it won't be an easy task

    request_count = 0

    def setup_main(self):
        self.requests = []

        end_time = datetime.datetime.now() + datetime.timedelta(seconds=10)

        while datetime.datetime.now() < end_time:

            self.requests.append(weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"}))
            self.request_count += 1

    def test_main(self):
        """send requests for 10 seconds, check that only 10-ish traces are sent, as rate limiter is set to 1/s"""

        MANUAL_KEEP = 2
        trace_count = 0

        for r in self.requests:
            for _, _, span, _ in interfaces.library.get_appsec_events(request=r):
                # the logic is to set MANUAL_KEEP not on all traces
                # then the sampling mechism drop, or not the traces
                if span["metrics"]["_sampling_priority_v1"] == MANUAL_KEEP:
                    trace_count += 1

        message = f"sent {self.request_count} in 10 s. Expecting to see 10 events but saw {trace_count} events"

        # very permissive test. We expect 10 traces, allow from 1 to 30.
        assert 1 <= trace_count <= 30, message
