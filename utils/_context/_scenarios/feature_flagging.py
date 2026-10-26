from ._core import DdTraceEndToEndScenario, scenario_groups


class FeatureFlaggingAndExperimentation(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "FEATURE_FLAGGING_AND_EXPERIMENTATION",
            rc_api_enabled=True,
            # Allow final EVP batches to reach the backend after the weblog flushes and stops.
            agent_interface_timeout=15,
            weblog_env={
                "DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED": "true",
                "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE": "remote_config",
                # set_provider() in Python blocks until we receive RC
                # configuration for feature flags. But it is only sent
                # after weblog sucessfully boots and tests start
                # executing. Unfortunately, Python's OpenFeature SDK does
                # not have "set provider and don't wait," so we reduce the
                # timeout here, so that the provider initialization fails
                # fast, weblog boots, and provider recovers when we set RC
                # configuration later.
                "DD_EXPERIMENTAL_FLAGGING_PROVIDER_INITIALIZATION_TIMEOUT_MS": "100",
                "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
                "DD_METRICS_OTEL_ENABLED": "true",
                "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL": "http/protobuf",
                "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT": "http://agent:4318/v1/metrics",
                "OTEL_METRIC_EXPORT_INTERVAL": "1000",
            },
            doc="",
            scenario_groups=[scenario_groups.ffe],
        )
