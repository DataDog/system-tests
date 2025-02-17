# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as debugger
import re
from utils import scenarios, features, missing_feature, bug, context

_OVERRIDE_APROVALS = debugger.get_env_bool("DI_OVERRIDE_APPROVALS")

@features.debugger
@scenarios.debugger_telemetry
class Test_Debugger_Telemetry(debugger._Base_Debugger_Test):
    telemetry = None
    telemetry_data = None

    ############ setup ############
    def _setup(self):
        if not Test_Debugger_Telemetry.telemetry_data:
            if self.get_tracer()["language"] == "dotnet":
                telemetry_type = "app-client-configuration-change"
            else:
                telemetry_type = "app-started"
                Test_Debugger_Telemetry.telemetry_data = self.wait_for_telemetry(telemetry_type)

        self.telemetry = Test_Debugger_Telemetry.telemetry_data
        
        
    ########### assert ############
    def _assert(self, product, pattern):
        def _extract_configurations(pattern):
            if "payload" in self.telemetry:
                configuration = self.telemetry["payload"]["configuration"]
            else:
                configuration = self.telemetry["configuration"]

            extracted = [
                [item["name"], item["origin"], item["value"]]
                for item in configuration
                if re.search(pattern, item["name"], re.IGNORECASE)
            ]

            return sorted(extracted, key=lambda x: x[0])

        def _validate_configurations(configs, product):
            assert configs, f"{product} configurations were not received"

            prefix = f"telemetry_{product}"
            self.write_approval(configs, prefix, "received")

            if _OVERRIDE_APROVALS:
                self.write_approval(configs, prefix, "configs_expected")

            expected_configs = self.read_approval(prefix, "configs_expected")
            assert expected_configs == configs

        assert self.telemetry, f"Telemetry for {product} was not received"

        _validate_configurations(_extract_configurations(pattern=pattern), product=product)
    
    ########### test ############
    ### Dynamic Instrumentation ###
    def setup_telemetry_di(self):
        self._setup()

    def test_telemetry_di(self):
        self._assert(product="di", pattern=r"dynamic[_]?instrumentation")

    ### Exception Replay ###
    def setup_telemetry_er(self):
        self._setup()

    @bug(context.library == "python", reason="DEBUG-3529")
    @missing_feature(context.library == "nodejs", reason="feature not implemented")
    @missing_feature(context.library == "php", reason="feature not implemented")
    def test_telemetry_er(self):
        self._assert(product="er", pattern=r"exception[_]?")

    ### SymDb ###
    def setup_telemetry_symdb(self):
        self._setup()

    @missing_feature(context.library == "nodejs", reason="feature not implemented")
    @missing_feature(context.library == "php", reason="feature not implemented")
    def test_telemetry_symdb(self):
        self._assert(product="symdb", pattern=r"symbol[_]?")

    ### Code Origin ###
    def setup_telemetry_co(self):
        self._setup()

    @missing_feature(context.library == "python", reason="feature not implemented")
    @missing_feature(context.library == "php", reason="feature not implemented")
    def test_telemetry_co(self):
        self._assert(product="co", pattern=r"code[_]?origin[_]?")
