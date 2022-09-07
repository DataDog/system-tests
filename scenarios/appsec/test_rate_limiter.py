# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, context, coverage, interfaces, released, rfc, bug
import pytest
import datetime

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@rfc("https://docs.google.com/document/d/1X64XQOk3N-aS_F0bJuZLkUiJqlYneDxo_b8WnkfFy_0")
@released(dotnet="2.6.0", nodejs="2.0.0")
@bug(weblog_variant="express4", reason="APPSEC-5427")
@coverage.basic
class Test_Main(BaseTestCase):
    """Basic tests for rate limiter"""

    # TODO: a scenario with DD_TRACE_SAMPLE_RATE set to something
    # as sampling mechnism is very different across agent, it won't be an easy task

    trace_count = 0
    request_count = 0

    def test_main(self):
        """send requests for 10 seconds, check that only 10-ish traces are sent, as rate limiter is set to 1/s"""

        MANUAL_KEEP = 2

        def count(span, appsec_data):
            # the logic is to set MANUAL_KEEP not on all traces
            # then the sampling mechism drop, or not the traces
            if span["metrics"]["_sampling_priority_v1"] == MANUAL_KEEP:
                self.trace_count += 1

        def validator():
            message = f"sent {self.request_count} in 10 s. Expecting to see 10 events but saw {self.trace_count} events"

            # very permissive test. We expect 10 traces, allow from 1 to 30.
            assert 1 <= self.trace_count <= 30, message

            return True

        end_time = datetime.datetime.now() + datetime.timedelta(seconds=10)

        while datetime.datetime.now() < end_time:
            r = self.weblog_get("/waf/", headers={"User-Agent": "Arachni/v1"})
            interfaces.library.add_appsec_validation(r, count, is_success_on_expiry=True)
            self.request_count += 1

        interfaces.library.add_final_validation(validator)
