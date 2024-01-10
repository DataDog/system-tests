# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import datetime
import time

from utils import (
    weblog,
    context,
    coverage,
    interfaces,
    rfc,
    bug,
    scenarios,
    flaky,
    features,
)
from utils.tools import logger


@rfc("https://docs.google.com/document/d/1X64XQOk3N-aS_F0bJuZLkUiJqlYneDxo_b8WnkfFy_0")
@bug(
    context.library in ("nodejs@3.2.0", "nodejs@2.15.0"), weblog_variant="express4", reason="APPSEC-5427",
)
@bug(
    context.library >= "php@0.92.0.dev", reason="AppSec need to update their dev version",
)
@coverage.basic
@scenarios.appsec_rate_limiter
@features.appsec_rate_limiter
class Test_Main:
    """Basic tests for rate limiter"""

    # TODO: a scenario with DD_TRACE_SAMPLE_RATE set to something
    # as sampling mechnism is very different across agent, it won't be an easy task

    def setup_main(self):
        """
            Make 5 requests per second, for 10 seconds.

            The test may be flaky if all requests takes more than 200ms, but it's very unlikely
        """
        self.requests = []

        start_time = datetime.datetime.now()

        for i in range(10):
            for _ in range(5):
                self.requests.append(weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"}))

            end_time = start_time + datetime.timedelta(seconds=i + 1)
            time.sleep(max(0, (end_time - datetime.datetime.now()).total_seconds()))

        logger.debug(f"Sent 50 requests in {(datetime.datetime.now() - start_time).total_seconds()} s")

    @bug(context.library > "nodejs@3.14.1", reason="_sampling_priority_v1 is missing")
    @flaky("rails" in context.weblog_variant, reason="APPSEC-10303")
    def test_main(self):
        """send requests for 10 seconds, check that only 10-ish traces are sent, as rate limiter is set to 1/s"""

        MANUAL_KEEP = 2
        trace_count = 0

        for r in self.requests:
            for data, _, span, _ in interfaces.library.get_appsec_events(request=r):
                # the logic is to set MANUAL_KEEP not on all traces
                # then the sampling mechism drop, or not the traces

                assert (
                    "_sampling_priority_v1" in span["metrics"]
                ), f"_sampling_priority_v1 is missing in span {span['span_id']} in {data['log_filename']}"

                if span["metrics"]["_sampling_priority_v1"] == MANUAL_KEEP:
                    trace_count += 1

        message = f"Sent 50 requests in 10 s. Expecting to see less than 10 events but saw {trace_count} events"

        # very permissive test. We expect 10 traces, allow from 1 to 30.
        assert 1 <= trace_count <= 30, message
