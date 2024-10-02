# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""singleton exposing all about test context"""

import json


class _Context:
    """ 
        Context is an helper class that exposes scenario properties
        Those properties may be used in decorators, and thus, should always exists, even if the current
        scenario does not define them.
    """

    scenario = None  # will be set by pytest_configure

    def _get_scenario_property(self, name, default):
        if hasattr(self.scenario, name):
            return getattr(self.scenario, name)

        return default

    @property
    def dd_site(self):
        return self._get_scenario_property("dd_site", None)

    @property
    def agent_version(self):
        return self._get_scenario_property("agent_version", "")

    @property
    def weblog_variant(self):
        return self._get_scenario_property("weblog_variant", "")

    @property
    def uds_mode(self):
        return self._get_scenario_property("uds_mode", None)

    @property
    def uds_socket(self):
        return self._get_scenario_property("uds_socket", None)

    @property
    def library(self):
        return self._get_scenario_property("library", None)

    @property
    def tracer_sampling_rate(self):
        return self._get_scenario_property("tracer_sampling_rate", None)

    @property
    def telemetry_heartbeat_interval(self):
        return self._get_scenario_property("telemetry_heartbeat_interval", None)

    @property
    def libddwaf_version(self):
        return self._get_scenario_property("libddwaf_version", "")

    @property
    def appsec_rules_file(self):
        return self._get_scenario_property("appsec_rules_file", "")

    @property
    def appsec_rules_version(self):
        return self._get_scenario_property("appsec_rules_version", "")

    @property
    def dd_apm_inject_version(self):
        return self._get_scenario_property("dd_apm_inject_version", "")

    @property
    def installed_language_runtime(self):
        return self._get_scenario_property("installed_language_runtime", "")

    @property
    def k8s_cluster_agent_version(self):
        return self._get_scenario_property("k8s_cluster_agent_version", "")

    @property
    def components(self):
        return self.scenario.components

    @property
    def parametrized_tests_metadata(self):
        return self.scenario.parametrized_tests_metadata

    @property
    def configuration(self):
        return self._get_scenario_property("configuration", {})

    def serialize(self):
        result = {
            "agent": str(self.agent_version),
            "library": self.library.serialize(),
            "weblog_variant": self.weblog_variant,
            "sampling_rate": self.tracer_sampling_rate,
            "libddwaf_version": str(self.libddwaf_version),
            "appsec_rules_file": self.appsec_rules_file or "*default*",
            "uds_socket": self.uds_socket,
            "scenario": self.scenario,
        }
        # TODO all components inside of components node
        result |= self.components

        # If a test is parametrized, it could contain specific data for each test. This node will contain this data associated with test id
        # If we are on multi thread environment we need to store this data on a file. We should deserialize json data (extract data from file)
        if self.parametrized_tests_metadata:
            try:
                result["parametrized_tests_metadata"] = self.parametrized_tests_metadata.deserialize()
            except AttributeError:
                result["parametrized_tests_metadata"] = self.parametrized_tests_metadata

        return result

    def __str__(self):
        return json.dumps(self.serialize(), indent=4)


context = _Context()
