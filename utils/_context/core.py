# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""singleton exposing all about test context"""

import json

from utils._context._scenarios import current_scenario


class _Context:
    """ context is an helper class that exposes directly everyting about tests targets """

    @property
    def scenario(self):
        return current_scenario.name

    @property
    def dd_site(self):
        return current_scenario.agent_container.dd_site

    @property
    def tracer_sampling_rate(self):
        return current_scenario.weblog_container.tracer_sampling_rate

    @property
    def appsec_rules_file(self):
        return current_scenario.weblog_container.appsec_rules_file

    @property
    def uds_socket(self):
        return current_scenario.weblog_container.uds_socket

    @property
    def library_version(self):
        return current_scenario.library_version

    @property
    def weblog_variant(self):
        return current_scenario.weblog_variant

    @property
    def php_appsec(self):
        return current_scenario.php_appsec

    @property
    def libddwaf_version(self):
        return current_scenario.weblog_container.libddwaf_version

    @property
    def appsec_rules_version(self):
        return current_scenario.weblog_container.appsec_rules_version

    @property
    def agent_version(self):
        return current_scenario.agent_version

    @property
    def uds_mode(self):
        return current_scenario.weblog_container.uds_mode

    @property
    def telemetry_heartbeat_interval(self):
        return current_scenario.weblog_container.telemetry_heartbeat_interval

    def serialize(self):
        result = {
            "agent": str(self.agent_version),
            "library": self.library_version.serialize(),
            "weblog_variant": self.weblog_variant,
            "dd_site": self.dd_site,
            "sampling_rate": self.tracer_sampling_rate,
            "libddwaf_version": str(self.libddwaf_version),
            "appsec_rules_file": self.appsec_rules_file or "*default*",
            "uds_socket": self.uds_socket,
            "scenario": self.scenario,
        }

        if self.library_version.library == "php":
            result["php_appsec"] = self.php_appsec

        return result

    def __str__(self):
        return json.dumps(self.serialize(), indent=4)


context = _Context()
