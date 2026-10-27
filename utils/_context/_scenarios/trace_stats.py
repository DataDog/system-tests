from ._core import DdTraceEndToEndScenario, scenario_groups


class TraceStatsComputation(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            name="TRACE_STATS_COMPUTATION",
            # feature consistency is poorly respected here ...
            weblog_env={
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "true",  # default env var for CSS
                "DD_TRACE_COMPUTE_STATS": "true",
                "DD_TRACE_FEATURES": "discovery",
                "DD_TRACE_TRACER_METRICS_ENABLED": "true",  # java
                "_DD_TRACE_STATS_COMPUTATION_EXPERIMENTAL_CLIENT_OBFUSCATION_ENABLED": "true",
            },
            doc=(
                "End to end testing with DD_TRACE_COMPUTE_STATS=1. This feature compute stats at tracer level, and"
                "may drop some of them"
            ),
            scenario_groups=[scenario_groups.appsec],
        )


class TraceStatsComputationClientDropP0sFalse(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            name="TRACE_STATS_COMPUTATION_CLIENT_DROP_P0S_FALSE",
            # Same as trace_stats_computation but with client_drop_p0s set to false
            # to test tracer behavior when agent doesn't support client-side P0 dropping
            weblog_env={
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "true",  # default env var for CSS
                "DD_TRACE_COMPUTE_STATS": "true",
                "DD_TRACE_FEATURES": "discovery",
                "DD_TRACE_TRACER_METRICS_ENABLED": "true",  # java
                "_DD_TRACE_STATS_COMPUTATION_EXPERIMENTAL_CLIENT_OBFUSCATION_ENABLED": "true",
            },
            client_drop_p0s=False,
            doc=(
                "End to end testing with DD_TRACE_COMPUTE_STATS=1 and agent reporting client_drop_p0s: false. "
                "Tests that tracers correctly disable stats computation when agent doesn't support client-side P0 "
                "dropping."
            ),
            scenario_groups=[scenario_groups.appsec],
        )


class TraceStatsComputationFutureObfuscationVersion(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            name="TRACE_STATS_COMPUTATION_FUTURE_OBFUSCATION_VERSION",
            # Same as trace_stats_computation but with the agent advertising an obfuscation_version
            # higher than what any current SDK supports (99), to test that the SDK correctly falls
            # back to no client-side obfuscation when it encounters an unknown/future version.
            weblog_env={
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "true",  # default env var for CSS
                "DD_TRACE_COMPUTE_STATS": "true",
                "DD_TRACE_FEATURES": "discovery",
                "DD_TRACE_TRACER_METRICS_ENABLED": "true",  # java
                "_DD_TRACE_STATS_COMPUTATION_EXPERIMENTAL_CLIENT_OBFUSCATION_ENABLED": "true",
            },
            obfuscation_version=99,
            doc=(
                "End to end testing with DD_TRACE_COMPUTE_STATS=1 and agent reporting obfuscation_version: 99. "
                "Tests that tracers correctly skip client-side obfuscation and omit the Datadog-Obfuscation-Version "
                "header when the agent advertises an obfuscation version higher than what the SDK supports."
            ),
            scenario_groups=[scenario_groups.appsec],
        )


class TraceStatsComputationMissingObfuscationVersion(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            name="TRACE_STATS_COMPUTATION_MISSING_OBFUSCATION_VERSION",
            # Same as trace_stats_computation but with the agent not advertising obfuscation_version
            # in /info, to test that the SDK correctly falls back to no client-side obfuscation.
            weblog_env={
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "true",  # default env var for CSS
                "DD_TRACE_COMPUTE_STATS": "true",
                "DD_TRACE_FEATURES": "discovery",
                "DD_TRACE_TRACER_METRICS_ENABLED": "true",  # java
                "_DD_TRACE_STATS_COMPUTATION_EXPERIMENTAL_CLIENT_OBFUSCATION_ENABLED": "true",
            },
            obfuscation_version="MISSING",
            doc=(
                "End to end testing with DD_TRACE_COMPUTE_STATS=1 and agent not advertising obfuscation_version. "
                "Tests that tracers correctly skip client-side obfuscation and omit the Datadog-Obfuscation-Version "
                "header when the agent does not advertise any obfuscation version."
            ),
            scenario_groups=[scenario_groups.appsec],
        )


class TraceStatsComputationObfuscationVersionZero(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            name="TRACE_STATS_COMPUTATION_OBFUSCATION_VERSION_ZERO",
            # Same as trace_stats_computation but with the agent advertising obfuscation_version=0,
            # to test that the SDK treats version 0 as "not supported" and skips client-side obfuscation.
            weblog_env={
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "true",  # default env var for CSS
                "DD_TRACE_COMPUTE_STATS": "true",
                "DD_TRACE_FEATURES": "discovery",
                "DD_TRACE_TRACER_METRICS_ENABLED": "true",  # java
                "_DD_TRACE_STATS_COMPUTATION_EXPERIMENTAL_CLIENT_OBFUSCATION_ENABLED": "true",
            },
            obfuscation_version=0,
            doc=(
                "End to end testing with DD_TRACE_COMPUTE_STATS=1 and agent reporting obfuscation_version: 0. "
                "Tests that tracers correctly skip client-side obfuscation and omit the Datadog-Obfuscation-Version "
                "header when the agent advertises obfuscation_version=0."
            ),
            scenario_groups=[scenario_groups.appsec],
        )


class TraceStatsComputationObfuscationDisabled(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            name="TRACE_STATS_COMPUTATION_OBFUSCATION_DISABLED",
            # Same as trace_stats_computation but with the agent being configured with obfuscation disabled, to test
            # that the SDK correctly reads the obfuscation config from agent's /info and respects it.
            weblog_env={
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "true",  # default env var for CSS
                "DD_TRACE_COMPUTE_STATS": "true",
                "DD_TRACE_FEATURES": "discovery",
                "DD_TRACE_TRACER_METRICS_ENABLED": "true",  # java
                "_DD_TRACE_STATS_COMPUTATION_EXPERIMENTAL_CLIENT_OBFUSCATION_ENABLED": "true",
            },
            agent_env={
                "DD_APM_SQL_OBFUSCATION_MODE": "normalize_only",
            },
            doc=("End to end testing with DD_TRACE_COMPUTE_STATS=1 and obfuscation disabled."),
            scenario_groups=[scenario_groups.appsec],
        )


class TraceStatsComputationErrorSampler(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            name="TRACE_STATS_COMPUTATION_ERROR_SAMPLER",
            # Same as trace_stats_computation but with the trace sample rate set to 0, so that all traces
            # are P0 and would normally be dropped by the tracer. Error traces must still be sent to the
            # agent, because the agent error sampler keeps a portion of them.
            weblog_env={
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "true",  # default env var for CSS
                "DD_TRACE_COMPUTE_STATS": "true",
                "DD_TRACE_FEATURES": "discovery",
                "DD_TRACE_TRACER_METRICS_ENABLED": "true",  # java
                "DD_TRACE_SAMPLE_RATE": "0",
            },
            doc=(
                "End to end testing with DD_TRACE_COMPUTE_STATS=1 and DD_TRACE_SAMPLE_RATE=0. "
                "Tests that traces containing errors are still sent to the agent even when sampling would drop them."
            ),
            scenario_groups=[scenario_groups.appsec],
        )
