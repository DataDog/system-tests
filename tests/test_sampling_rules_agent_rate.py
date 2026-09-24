# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import time

from utils import weblog, interfaces, scenarios, features, logger
from utils.proxy.mocked_response import SequentialJsonMockedTracerResponse, send_mocked_tracer_responses


AGENT_RATE = 0.3


@scenarios.sampling_rules_agent_rate
@features.ensure_that_sampling_is_consistent_across_languages
class Test_SamplingRulesAgentRate:
    """When DD_TRACE_SAMPLING_RULES is configured, spans that don't match any rule fall back to the
    agent-driven rate-by-service sampler. That fallback must keep receiving the rates published by the
    agent, instead of being stuck at its default rate of 1.0 for the life of the process.

    Regression test for https://github.com/DataDog/dd-trace-java/pull/12490: the configured sampling
    rule ("not-the-real-service-xyz") never matches the weblog's actual service, so every span here is
    a rule-miss and must reflect the agent-published rate.
    """

    def setup_agent_rate_applies_to_rule_miss(self):
        mocked_json = {"rate_by_service": {"service:,env:": AGENT_RATE}}
        mocks = [
            SequentialJsonMockedTracerResponse(path="/v0.4/traces", mocked_json_sequence=[mocked_json]),
            SequentialJsonMockedTracerResponse(path="/v0.5/traces", mocked_json_sequence=[mocked_json]),
            # dd-trace-go (and possibly newer versions of other tracers) submits traces via this
            # newer endpoint instead of /v0.4 or /v0.5.
            SequentialJsonMockedTracerResponse(path="/v1.0/traces", mocked_json_sequence=[mocked_json]),
        ]
        send_mocked_tracer_responses(mocks)

        def has_agent_rate(_data: dict) -> bool:
            for _, span in interfaces.library.get_root_spans():
                agent_psr = span.get("metrics", {}).get("_dd.agent_psr")
                if agent_psr is not None and abs(agent_psr - AGENT_RATE) < 0.01:
                    return True
            return False

        # Generate traffic in bursts, none of it matching the configured sampling rule, so it all
        # goes through the rule-miss fallback sampler. A single burst isn't enough: the agent rate
        # is only visible in the *response* to a trace flush, so spans created before that response
        # round-trips back to the tracer still carry the old rate. Keep sending bursts, with pauses
        # to let a flush/response cycle happen, until a span shows the mocked agent rate.
        request_idx = 0
        for _ in range(15):
            if interfaces.library.wait_for(has_agent_rate, timeout=0):
                break
            for _j in range(20):
                weblog.get(f"/sample_rate_route/{request_idx}")
                request_idx += 1
            time.sleep(2)

        interfaces.library.wait_for(has_agent_rate, timeout=30)

    def test_agent_rate_applies_to_rule_miss(self):
        """Verify a rule-miss span carries the agent-published rate, not the default of 1.0."""
        agent_psr_values = {
            round(agent_psr, 4)
            for _, span in interfaces.library.get_root_spans()
            if (agent_psr := span.get("metrics", {}).get("_dd.agent_psr")) is not None
        }

        logger.info(f"Observed _dd.agent_psr values: {sorted(agent_psr_values)}")

        assert any(abs(v - AGENT_RATE) < 0.01 for v in agent_psr_values), (
            f"Expected to see the agent-published rate ({AGENT_RATE}) in _dd.agent_psr values on "
            f"rule-miss spans, but only saw: {sorted(agent_psr_values)}. The fallback sampler used for "
            "spans that don't match any DD_TRACE_SAMPLING_RULES entry must still receive agent rates."
        )
