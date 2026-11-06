from ._core import DdTraceEndToEndScenario, scenario_groups


class Sampling(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "SAMPLING",
            appsec_enabled=False,
            iast_enabled=False,
            tracer_sampling_rate=0.5,
            weblog_env={"DD_TRACE_RATE_LIMIT": "10000000", "DD_TRACE_STATS_COMPUTATION_ENABLED": "false"},
            doc="Test sampling mechanism. Not included in default scenario because it's a little bit too flaky",
            scenario_groups=[scenario_groups.sampling],
        )


class SamplingRateCapping(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "SAMPLING_RATE_CAPPING",
            weblog_env={"DD_TRACE_RATE_LIMIT": "10000000", "DD_TRACE_STATS_COMPUTATION_ENABLED": "false"},
            doc="Test that tracers cap sampling rate increases to 2x per interval when agent restarts",
            scenario_groups=[scenario_groups.sampling],
        )


class SamplingRulesAgentRate(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "SAMPLING_RULES_AGENT_RATE",
            weblog_env={
                "DD_TRACE_RATE_LIMIT": "10000000",
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "false",
                # This rule never matches real weblog traffic (wrong service name), so every span
                # falls through to the fallback sampler. That fallback must still receive agent-published
                # rates instead of being stuck at 1.0: https://github.com/DataDog/dd-trace-java/pull/12490
                "DD_TRACE_SAMPLING_RULES": '[{"service": "not-the-real-service-xyz", "sample_rate": 1.0}]',
            },
            doc=(
                "Test that agent-published sampling rates are still applied to spans that don't match any "
                "configured sampling rule, instead of the rule-miss fallback being stuck at rate 1.0."
            ),
            scenario_groups=[scenario_groups.sampling],
        )
