# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import scenarios, features, context, interfaces, missing_feature
from utils import remote_config as rc


CONFIG_ENABLED = {"asm": {"enabled": True}}
CONFIG_DISABLED = {"asm": {"enabled": False}}


def _send_config(config):
    """Send remote configuration to enable/disable AppSec features"""
    if config is not None:
        rc.rc_state.set_config("datadog/2/ASM_FEATURES/asm_features_activation/config", config)
    else:
        rc.rc_state.reset()
    return rc.rc_state.apply().state


def validate_telemetry_configuration(telemetry_data, expected_config_name, expected_value, expected_origin=None):
    """Validate that telemetry configuration contains the expected appsec.enabled value and origin"""
    for data in telemetry_data:
        if data["request"]["content"].get("request_type") == "app-client-configuration-change":
            content = data["request"]["content"]
            configurations = content["payload"]["configuration"]

            for config in configurations:
                if config.get("name") == expected_config_name:
                    # Check if the configuration has the expected value
                    # Handle both boolean and string values
                    config_value = config.get("value")
                    value_matches = config_value == expected_value or str(config_value).lower() == str(expected_value).lower()
                    
                    # Check origin if specified
                    origin_matches = True
                    if expected_origin is not None:
                        config_origin = config.get("origin")
                        origin_matches = config_origin == expected_origin
                    
                    if value_matches and origin_matches:
                        return True

    return False


class BaseTelemetryAppSecConfiguration:
    """Base class for testing telemetry configuration with AppSec enabled/disabled"""

    expected_value: bool | None = None
    expected_origin: str = ""

    @missing_feature(context.library in ("php",), reason="Telemetry is not implemented yet.")
    @missing_feature(context.library < "ruby@1.22.0", reason="Telemetry V2 is not implemented yet")
    def test_telemetry_appsec_configuration(self):
        """Test that telemetry configuration correctly reports appsec.enabled value"""
        telemetry_data = list(interfaces.library.get_telemetry_data())

        assert len(telemetry_data) > 0, "No telemetry data found"

        expected_config_name = "appsec_enabled"

        # Debug: Print all configurations to see what's actually there
        for data in telemetry_data:
            if data["request"]["content"].get("request_type") == "app-client-configuration-change":
                content = data["request"]["content"]
                configurations = content["payload"]["configuration"]
                print(f"Found configurations: {[c.get('name') for c in configurations]}")
                for config in configurations:
                    if "appsec" in config.get("name", ""):
                        print(f"AppSec config: {config}")

        # Validate that the configuration is present with the expected value and origin
        config_found = validate_telemetry_configuration(
            telemetry_data, expected_config_name, self.expected_value, self.expected_origin
        )

        assert config_found, (
            f"Telemetry configuration '{expected_config_name}' with value '{self.expected_value}' "
            f"and origin '{self.expected_origin}' not found in app-client-configuration-change event"
        )


@scenarios.appsec_runtime_activation
@features.telemetry_app_started_event
@features.telemetry_configurations_collected
class TestTelemetryAppSecRemoteConfigEnabled(BaseTelemetryAppSecConfiguration):
    """Test that telemetry configuration correctly reports appsec.enabled=true when enabled via remote config"""

    def setup_telemetry_appsec_configuration(self):
        self.expected_value = True
        self.expected_origin = "remote_config"
        self.config_state = _send_config(CONFIG_ENABLED)
