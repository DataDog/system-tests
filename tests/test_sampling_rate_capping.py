# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import time

import requests

from utils import weblog, interfaces, scenarios, features, logger
from utils.proxy.mocked_response import (
    MOCKED_TRACER_RESPONSES_PATH,
    SequentialJsonMockedTracerResponse,
    _get_proxy_domain,
)
from utils.proxy.ports import ProxyPorts


LOW_RATE = 0.1
HIGH_RATE = 1.0


def _send_mocked_tracer_responses(mocks: list) -> None:
    """Send multiple mocked tracer responses in a single PUT request."""
    domain = _get_proxy_domain()
    response = requests.put(
        f"http://{domain}:{ProxyPorts.proxy_commands}{MOCKED_TRACER_RESPONSES_PATH}",
        json=[m.to_json() for m in mocks],
        timeout=30,
    )
    response.raise_for_status()


@scenarios.sampling_rate_capping
@features.ensure_that_sampling_is_consistent_across_languages
class Test_SamplingRateCappedIncrease:
    """When the agent returns a new higher sampling rate, the tracer should not jump directly
    to the new rate. Instead, it should cap increases to 2x per flush interval, ramping up
    gradually (e.g. 0.1 -> 0.2 -> 0.4 -> 0.8 -> 1.0).
    """

    NUM_LOW_RATE_RESPONSES = 12
    NUM_HIGH_RATE_RESPONSES = 20

    def setup_sampling_rate_capped_increase(self):
        low_rate_response = {"rate_by_service": {"service:,env:": LOW_RATE}}
        high_rate_response = {"rate_by_service": {"service:,env:": HIGH_RATE}}

        sequence = [low_rate_response] * self.NUM_LOW_RATE_RESPONSES + [
            high_rate_response
        ] * self.NUM_HIGH_RATE_RESPONSES

        # Send mocks for both trace endpoints in one call to avoid overwriting
        mocks = [
            SequentialJsonMockedTracerResponse(path="/v0.4/traces", mocked_json_sequence=sequence),
            SequentialJsonMockedTracerResponse(path="/v0.5/traces", mocked_json_sequence=sequence),
        ]
        _send_mocked_tracer_responses(mocks)

        # Generate initial traffic until the tracer picks up the low rate
        for i in range(40):
            weblog.get(f"/sample_rate_route/{i}")

        # Wait for a span with the low agent_psr to appear
        def wait_for_low_rate(_data: dict) -> bool:
            for _, span in interfaces.library.get_root_spans():
                agent_psr = span.get("metrics", {}).get("_dd.agent_psr")
                if agent_psr is not None and abs(agent_psr - LOW_RATE) < 0.01:
                    return True
            return False

        interfaces.library.wait_for(wait_for_low_rate, timeout=30)

        # Generate traffic in bursts to trigger multiple flush cycles during ramp-up
        request_idx = 100
        for _ in range(6):
            for _j in range(20):
                weblog.get(f"/sample_rate_route/{request_idx}")
                request_idx += 1
            time.sleep(1.5)

        # Wait for the tracer to ramp up to the high rate
        def wait_for_high_rate(_data: dict) -> bool:
            for _, span in interfaces.library.get_root_spans():
                agent_psr = span.get("metrics", {}).get("_dd.agent_psr")
                if agent_psr is not None and abs(agent_psr - HIGH_RATE) < 0.01:
                    return True
            return False

        interfaces.library.wait_for(wait_for_high_rate, timeout=30)

    def test_sampling_rate_capped_increase(self):
        """Verify that the tracer ramps up sampling rate gradually instead of jumping directly."""
        agent_psr_values = set()

        for _, span in interfaces.library.get_root_spans():
            agent_psr = span.get("metrics", {}).get("_dd.agent_psr")
            if agent_psr is not None:
                agent_psr_values.add(round(agent_psr, 4))

        logger.info(f"Observed _dd.agent_psr values: {sorted(agent_psr_values)}")

        assert any(abs(v - LOW_RATE) < 0.01 for v in agent_psr_values), (
            f"Expected to see the low rate ({LOW_RATE}) in _dd.agent_psr values: {sorted(agent_psr_values)}"
        )
        assert any(abs(v - HIGH_RATE) < 0.01 for v in agent_psr_values), (
            f"Expected to see the high rate ({HIGH_RATE}) in _dd.agent_psr values: {sorted(agent_psr_values)}"
        )

        # Key assertion: at least one intermediate value strictly between LOW_RATE and HIGH_RATE
        intermediate_values = [v for v in agent_psr_values if LOW_RATE + 0.01 < v < HIGH_RATE - 0.01]
        assert len(intermediate_values) > 0, (
            f"Expected at least one intermediate _dd.agent_psr value between {LOW_RATE} and {HIGH_RATE}, "
            f"but only saw: {sorted(agent_psr_values)}. "
            "The tracer should cap sampling rate increases to 2x per interval, not jump directly."
        )
