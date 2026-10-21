# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from typing import Any

import tests.debugger.utils as debugger
from utils import features, logger, scenarios, slow
from utils.telemetry import load_telemetry_json, get_lang_configs

ALLOWED_ORIGINS = {"env_var", "code", "dd_config", "remote_config", "app.config", "default", "unknown"}


@features.debugger
@scenarios.debugger_telemetry
class Test_Debugger_Telemetry(debugger.BaseDebuggerTest):
    telemetry: dict | None
    telemetry_data: dict | None = None

    ############ setup ############
    def _load_normalization_rules(self) -> None:
        # Load the telemetry intake general and language-specific configuration normalization rules.
        self.config_norm_rules = load_telemetry_json("config_norm_rules")
        self.lang_configs = get_lang_configs()
        self.lang_configs["java"] = self.lang_configs["jvm"]

    def _setup(self):
        self._load_normalization_rules()

        if not Test_Debugger_Telemetry.telemetry_data:
            telemetry_type = "app-started"

            if self.get_tracer()["language"] in ("dotnet", "php"):
                telemetry_type = "app-client-configuration-change"

            Test_Debugger_Telemetry.telemetry_data = self.wait_for_telemetry(telemetry_type)

        self.telemetry = Test_Debugger_Telemetry.telemetry_data

    def _canonical_config_name(self, name: str) -> str | None:
        lowered = name.lower()
        language = self.get_tracer()["language"]
        if lowered in self.lang_configs[language]:
            return self.lang_configs[language][lowered]
        if lowered in self.config_norm_rules:
            return self.config_norm_rules[lowered]
        return None

    ########### assert ############
    def _assert(self, required_telemetry: list[str]):
        """Assert that telemetry was received, that the required telemetry (after normalization) is present, and that
        the origin of the telemetry is one of the allowed origins.
        """
        assert self.telemetry, "Telemetry was not received"

        if "payload" in self.telemetry:
            configuration = self.telemetry["payload"]["configuration"]
        else:
            configuration = self.telemetry["configuration"]

        # Normalize the telemetry names using the configuration normalization rules.
        normalized: dict[str, tuple[str | None, Any]] = {}
        for item in configuration:
            name = self._canonical_config_name(item["name"])
            if name is None:
                logger.warning(f"Unmapped telemetry name: {item['name'].lower()}")
                continue

            # Store the origin and and value for future validation.
            normalized[name] = (item.get("origin", None), item.get("value", None))

        for required in required_telemetry:
            assert required in normalized, f"{required} telemetry not received"
            origin, _ = normalized[required]
            assert origin in ALLOWED_ORIGINS, f"{required} telemetry origin {origin} not in {ALLOWED_ORIGINS}"
            if origin != "env_var":
                logger.warning(f"{required} telemetry origin {origin} not 'env_var' as expected")

    ########### test ############
    ### Dynamic Instrumentation ###
    def setup_telemetry_di(self):
        self._setup()

    def test_telemetry_di(self):
        self._assert(required_telemetry=["dynamic_instrumentation_enabled"])

    # ### Exception Replay ###
    def setup_telemetry_er(self):
        # The key is on app-started or the next configuration-change, so it cannot use the shared payload.
        self._load_normalization_rules()
        self.telemetry = self.wait_for_startup_telemetry(
            lambda configuration: any(
                self._canonical_config_name(item["name"]) == "exception_replay_enabled" for item in configuration
            )
        )

    @slow
    def test_telemetry_er(self):
        self._assert(required_telemetry=["exception_replay_enabled"])

    # ### SymDb ###
    def setup_telemetry_symdb(self):
        self._setup()

    @slow
    def test_telemetry_symdb(self):
        self._assert(required_telemetry=["symbol_database_upload_enabled"])

    # ### Code Origin ###
    def setup_telemetry_co(self):
        self._setup()

    @slow
    def test_telemetry_co(self):
        self._assert(required_telemetry=["code_origin_for_spans_enabled"])
