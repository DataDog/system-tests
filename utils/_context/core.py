# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""singleton exposing all about test context"""

import json
from typing import Any

from utils._context.component_version import ComponentVersion, Version
from utils._context._scenarios.core import Scenario
from utils._context._scenarios.endtoend import DockerScenario
from utils.virtual_machine.virtual_machines import _VirtualMachine
from utils._context.containers import SqlDbTestedContainer


class _Context:
    """Context is an helper class that exposes scenario properties
    Those properties may be used in decorators, and thus, should always exists, even if the current
    scenario does not define them.
    """

    scenario: Scenario  # will be set by pytest_configure

    def _get_scenario_property(self, name: str, default: Any) -> Any:  # noqa:ANN401
        if hasattr(self.scenario, name):
            return getattr(self.scenario, name)

        return default

    @property
    def dd_site(self) -> str:
        return self._get_scenario_property("dd_site", "")

    @property
    def agent_version(self) -> Version:
        return self._get_scenario_property("agent_version", Version("0.0.0"))

    @property
    def weblog_variant(self) -> str:
        return self._get_scenario_property("weblog_variant", "")

    @property
    def uds_mode(self):
        return self._get_scenario_property("uds_mode", None)

    @property
    def uds_socket(self):
        return self._get_scenario_property("uds_socket", None)

    @property
    def library(self) -> ComponentVersion:
        result = self._get_scenario_property("library", None)
        assert result is not None
        return result

    @property
    def tracer_sampling_rate(self):
        return self._get_scenario_property("tracer_sampling_rate", None)

    @property
    def telemetry_heartbeat_interval(self):
        return self._get_scenario_property("telemetry_heartbeat_interval", None)

    @property
    def appsec_rules_file(self):
        return self._get_scenario_property("appsec_rules_file", "")

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
    def components(self) -> dict[str, str]:
        assert self.scenario is not None
        return self.scenario.components

    @property
    def parametrized_tests_metadata(self):
        return self.scenario.parametrized_tests_metadata

    @property
    def configuration(self):
        return self._get_scenario_property("configuration", {})

    @property
    def virtual_machine(self) -> _VirtualMachine:
        return self._get_scenario_property(
            "virtual_machine",
            _VirtualMachine(
                name="",
                aws_config=None,
                vagrant_config=None,
                krunvm_config=None,
                os_type=None,
                os_distro=None,
                os_branch="",
                os_cpu="",
            ),
        )

    @property
    def vm_os_branch(self) -> str:
        return self.virtual_machine.os_branch

    @property
    def vm_os_cpu(self) -> str:
        return self.virtual_machine.os_cpu

    @property
    def vm_name(self) -> str:
        return self.virtual_machine.name

    @property
    def k8s_scenario_provision(self) -> str:
        return self._get_scenario_property("current_scenario_provision", {})

    def serialize(self):
        result = {
            "weblog_variant": self.weblog_variant,
            "sampling_rate": self.tracer_sampling_rate,
            "appsec_rules_file": self.appsec_rules_file or "*default*",
            "uds_socket": self.uds_socket,
            "scenario": self.scenario,
        }
        # TODO all components inside of components node
        result |= self.components

        # If a test is parametrized, it could contain specific data for each test. This node will contain this data
        # associated with test id. If we are on multi thread environment we need to store this data on a file.
        # We should deserialize json data (extract data from file)
        if self.parametrized_tests_metadata:
            try:
                result["parametrized_tests_metadata"] = self.parametrized_tests_metadata.deserialize()
            except AttributeError:
                result["parametrized_tests_metadata"] = self.parametrized_tests_metadata

        return result

    def get_container_by_dd_integration_name(self, name: str) -> SqlDbTestedContainer:
        assert isinstance(self.scenario, DockerScenario)
        container = self.scenario.get_container_by_dd_integration_name(name)
        assert container is not None
        return container

    def __str__(self):
        return json.dumps(self.serialize(), indent=4)


context = _Context()
