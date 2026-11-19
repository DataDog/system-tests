from ._core import DdTraceEndToEndScenario, scenario_groups


class AgentSupportingSpanEvents(DdTraceEndToEndScenario):
    """The trace agent support Span Events and it is enabled through an environment variable"""

    def __init__(self) -> None:
        super().__init__(
            "AGENT_SUPPORTING_SPAN_EVENTS",
            weblog_env={"DD_TRACE_NATIVE_SPAN_EVENTS": "1", "DD_TELEMETRY_METRICS_ENABLED": "true"},
            span_events=True,
            scenario_groups=[scenario_groups.integrations, scenario_groups.telemetry],
        )


class AgentNotSupportingSpanEvents(DdTraceEndToEndScenario):
    """The trace agent does not support Span Events as a top-level span field"""

    def __init__(self) -> None:
        super().__init__(
            "AGENT_NOT_SUPPORTING_SPAN_EVENTS",
            weblog_env={"DD_TRACE_NATIVE_SPAN_EVENTS": "0"},
            span_events=False,
            scenario_groups=[scenario_groups.integrations],
        )
