"""Custom OpenTelemetry container classes for enhanced configurations"""

from utils._context.containers import OpenTelemetryCollectorContainer


class PostgresOpenTelemetryCollectorContainer(OpenTelemetryCollectorContainer):
    """OpenTelemetry Collector container with PostgreSQL receiver support
    Uses static merged configuration file
    """

    def __init__(self, host_log_folder: str, config_file: str | None = None) -> None:
        # Set default config file to the one with PostgreSQL support
        if config_file is None:
            config_file = "./utils/build/docker/otelcol-config-with-postgres.yaml"

        # Initialize parent class but override config path
        super().__init__(host_log_folder)

        # Override the config file path
        self._otel_config_host_path = config_file

        # Update the volumes mapping
        self.volumes = {self._otel_config_host_path: {"bind": "/etc/otelcol-config.yml", "mode": "ro"}}
