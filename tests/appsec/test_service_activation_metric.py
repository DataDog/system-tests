# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import scenarios
from utils import features
from utils import remote_config as rc
from tests.appsec.utils import find_series
from tests.appsec.utils import find_configuration

CONFIG_ENABLED = {"asm": {"enabled": True}}


def _send_config(config):
    if config is not None:
        rc.rc_state.set_config("datadog/2/ASM_FEATURES/asm_features_activation/config", config)
    else:
        rc.rc_state.reset()
    return rc.rc_state.apply().state


def validate_metric_tag(origin, metric):
    return metric.get("type") == "gauge" and f"origin:{origin}" in metric.get("tags", ())


class BaseServiceActivationMetric:
    origin = ""

    def test_service_activation_metric(self):
        series = find_series("appsec", ["enabled"])

        assert series
        assert any(validate_metric_tag(self.origin, s) for s in series), [s.get("tags") for s in series]


@scenarios.appsec_runtime_activation
@features.appsec_service_activation_origin_metric
class TestServiceActivationRemoteConfigMetric(BaseServiceActivationMetric):
    """Test that the service activation remote config metric is sent"""

    def setup_service_activation_metric(self):
        self.origin = "remote_config"
        self.config_state = _send_config(CONFIG_ENABLED)


@features.appsec_service_activation_origin_metric
class TestServiceActivationEnvVarMetric(BaseServiceActivationMetric):
    """Test that the service activation env var metric is sent"""

    def setup_service_activation_metric(self):
        self.origin = "env_var"


class BaseServiceActivationConfigurationMetric:
    origin = ""

    def test_service_activation_metric(self):
        assert any(
            c["origin"] == self.origin
            and (c["name"] == "DD_APPSEC_ENABLED" or c["name"] == "appsec.enabled")
            and c["value"] in ["1", 1, True]
            for payload_configuration in find_configuration()
            for c in payload_configuration
        )


@scenarios.appsec_runtime_activation
@features.appsec_service_activation_origin_metric
class TestServiceActivationRemoteConfigurationConfigMetric(BaseServiceActivationConfigurationMetric):
    """Test that the service activation remote config metric is sent"""

    def setup_service_activation_metric(self):
        self.origin = "remote_config"
        self.config_state = _send_config(CONFIG_ENABLED)


@features.appsec_service_activation_origin_metric
class TestServiceActivationEnvVarConfigurationMetric(BaseServiceActivationConfigurationMetric):
    """Test that the service activation env var metric is sent"""

    def setup_service_activation_metric(self):
        self.origin = "env_var"
