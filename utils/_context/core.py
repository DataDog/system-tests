# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""singleton exposing all about test context"""

import json


class _Context:
    """context is an helper class that exposes directly everyting about tests targets"""

    scenario = None  # will be set by pytest_configure

    @property
    def dd_site(self):
        return self.scenario.dd_site

    @property
    def tracer_sampling_rate(self):
        return self.scenario.tracer_sampling_rate

    @property
    def appsec_rules_file(self):
        return self.scenario.appsec_rules_file

    @property
    def uds_socket(self):
        return self.scenario.uds_socket

    @property
    def library(self):
        return self.scenario.library

    @property
    def weblog_variant(self):
        return self.scenario.weblog_variant

    @property
    def libddwaf_version(self):
        return self.scenario.libddwaf_version

    @property
    def appsec_rules_version(self):
        return self.scenario.appsec_rules_version

    @property
    def agent_version(self):
        return self.scenario.agent_version

    @property
    def uds_mode(self):
        return self.scenario.uds_mode

    @property
    def telemetry_heartbeat_interval(self):
        return self.scenario.telemetry_heartbeat_interval

    @property
    def components(self):
        return self.scenario.components

    @property
    def parametrized_tests_metadata(self):
        return self.scenario.parametrized_tests_metadata

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
