import pytest

from ._core import DdTraceEndToEndScenario, ScenarioGroup, scenario_groups

# Shared by the ordinary FFE scenario, the isolated EVP stress scenario, and both
# evaluation telemetry opt-out scenarios.
# Both opt-out scenarios also enable span enrichment; one enables the opt-out option.
_FFE_WEBLOG_ENV: dict[str, str | None] = {
    "DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED": "true",
    "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE": "remote_config",
    # Python's set_provider() waits for Remote Configuration, which arrives only
    # after the weblog starts. The OpenFeature API has no nonblocking alternative.
    # Fail initialization promptly so the weblog starts; the provider recovers
    # when the tests supply Remote Configuration.
    "DD_EXPERIMENTAL_FLAGGING_PROVIDER_INITIALIZATION_TIMEOUT_MS": "100",
    "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
    "DD_METRICS_OTEL_ENABLED": "true",
    "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL": "http/protobuf",
    "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT": "http://agent:4318/v1/metrics",
    "OTEL_METRIC_EXPORT_INTERVAL": "1000",
}


class FeatureFlaggingAndExperimentation(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "FEATURE_FLAGGING_AND_EXPERIMENTATION",
            rc_api_enabled=True,
            # Allow final EVP batches to reach the backend after the weblog flushes and stops.
            agent_interface_timeout=15,
            weblog_env=_FFE_WEBLOG_ENV,
            doc="",
            scenario_groups=[scenario_groups.ffe],
        )


class _ProvisionalFeatureFlaggingScenario(DdTraceEndToEndScenario):
    """Allow explicit FFE runs without scheduling unsupported SDKs in default CI."""

    _default_scenario_groups: tuple[ScenarioGroup, ...] = ()


class FeatureFlaggingEvaluationTelemetryOptOut(_ProvisionalFeatureFlaggingScenario):
    def __init__(self) -> None:
        super().__init__(
            "FEATURE_FLAGGING_EVALUATION_TELEMETRY_OPT_OUT",
            rc_api_enabled=True,
            agent_interface_timeout=15,
            weblog_env={
                **_FFE_WEBLOG_ENV,
                "DD_EXPERIMENTAL_FLAGGING_PROVIDER_SPAN_ENRICHMENT_ENABLED": "true",
                "DD_FEATURE_FLAGS_EVALUATION_TELEMETRY_PER_SUBJECT_OPT_OUT_ENABLED": "true",
            },
            doc="Per-subject evaluation telemetry opt-out, with unchanged assignments and exposures.",
            scenario_groups=[scenario_groups.ffe],
        )


class FeatureFlaggingEvaluationTelemetryOptOutDisabled(_ProvisionalFeatureFlaggingScenario):
    def __init__(self) -> None:
        super().__init__(
            "FEATURE_FLAGGING_EVALUATION_TELEMETRY_OPT_OUT_DISABLED",
            rc_api_enabled=True,
            agent_interface_timeout=15,
            weblog_env={
                **_FFE_WEBLOG_ENV,
                "DD_EXPERIMENTAL_FLAGGING_PROVIDER_SPAN_ENRICHMENT_ENABLED": "true",
                # Omit the opt-out option: an attribute must not activate the feature by itself.
            },
            doc="Default-disabled control for per-subject evaluation telemetry opt-out.",
            scenario_groups=[scenario_groups.ffe],
        )


class FeatureFlaggingEvpStress(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "FEATURE_FLAGGING_EVP_STRESS",
            rc_api_enabled=True,
            agent_interface_timeout=15,
            weblog_env=_FFE_WEBLOG_ENV,
            doc="Isolated high-cardinality EVP accounting: delivered evaluations plus reported capacity drops.",
            scenario_groups=[scenario_groups.ffe],
        )

    def configure(self, config: pytest.Config) -> None:
        super().configure(config)
        # Allow an EVP flush (Go: 10 s) plus the telemetry heartbeat (2 s) before stopping.
        # Preserve longer language-specific waits.
        self.library_interface_timeout = max(self.library_interface_timeout, 15)
