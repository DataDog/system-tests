# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as debugger
from utils import features, interfaces, logger, scenarios, slow, weblog
from utils.telemetry import load_telemetry_json, get_lang_configs

ALLOWED_ORIGINS = {"env_var", "code", "dd_config", "remote_config", "app.config", "default", "unknown"}

DEBUGGER_METRICS_NAMESPACE = "debugger"
# Namespaces that tracers used for debugger metrics before agreeing on `debugger`. The intake drops metrics sent in them.
LEGACY_DEBUGGER_METRICS_NAMESPACES = ("live_debugger", "dynamic_instrumentation")
METRICS_REQUEST_TYPES = ("generate-metrics", "distributions", "sketches")
# The probe's own rate limit, set through the `snapshotsPerSecond` sampling field, which also applies to log probes that
# don't capture a snapshot. Coordinated sampling exempts snapshot probes from their own rate limit inside a trace, but
# every tracer still rate limits these log probes on their own.
PROBE_EVENTS_PER_SECOND = 1
# Java and .NET rate limit probes with an adaptive sampler that also lets a probe spend an unused budget of 16 more
# events. A quick burst of this many hits exceeds that budget, so every tracer skips events because of the probe rate
# limit.
RATE_LIMIT_BURST_SIZE = 50


def _get_metric_series(namespace: str) -> list[dict]:
    """Return every telemetry metric series that the tracer sent in the given namespace."""
    series_list: list[dict] = []
    for data in interfaces.library.get_telemetry_data():
        content = data["request"]["content"]
        if content.get("request_type") not in METRICS_REQUEST_TYPES:
            continue
        payload = content["payload"]
        series_list.extend(
            series
            for series in payload.get("series", [])
            if series.get("namespace", payload.get("namespace")) == namespace
        )
    return series_list


def _get_rate_limit_probe_skips() -> list[dict]:
    # Datadog lowercases tags, and Python already sends them lowercased, so they're compared case-insensitively.
    return [
        series
        for series in _get_metric_series(DEBUGGER_METRICS_NAMESPACE)
        if series["metric"] == "events.skipped"
        and "reason:ratelimitprobe" in (tag.lower() for tag in series.get("tags", []))
    ]


@features.debugger
@scenarios.debugger_telemetry
class Test_Debugger_Telemetry(debugger.BaseDebuggerTest):
    telemetry: dict | None
    telemetry_data: dict | None = None

    ############ setup ############
    def _setup(self):
        # Load the telemetry intake general and language-specific configuration normalization rules.
        self.config_norm_rules = load_telemetry_json("config_norm_rules")
        self.lang_configs = get_lang_configs()
        self.lang_configs["java"] = self.lang_configs["jvm"]

        if not Test_Debugger_Telemetry.telemetry_data:
            telemetry_type = "app-started"

            if self.get_tracer()["language"] in ("dotnet", "php"):
                telemetry_type = "app-client-configuration-change"

            Test_Debugger_Telemetry.telemetry_data = self.wait_for_telemetry(telemetry_type)

        self.telemetry = Test_Debugger_Telemetry.telemetry_data

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
        language = self.get_tracer()["language"]
        normalized = {}
        for item in configuration:
            name = item["name"].lower()
            if name not in self.lang_configs[language] and name not in self.config_norm_rules:
                logger.warning(f"Unmapped telemetry name: {name}")
            elif name in self.lang_configs[language]:
                name = self.lang_configs[language][name]
            else:
                name = self.config_norm_rules[name]

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
        self._setup()

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


@features.debugger
@scenarios.debugger_telemetry
@slow
class Test_Debugger_Telemetry_Metrics(debugger.BaseDebuggerTest):
    """Debugger metrics are sent through instrumentation telemetry in the `debugger` namespace shared by all tracers."""

    def setup_events_skipped_rate_limit_probe(self):
        self.initialize_weblog_remote_config()

        probes = debugger.read_probes("probe_status_log_line")
        for probe in probes:
            probe["id"] = debugger.generate_probe_id("log")
            probe["sampling"] = {"snapshotsPerSecond": PROBE_EVENTS_PER_SECOND}
        self.set_probes(probes)

        self.send_rc_probes()
        if not self.wait_for_all_probes(statuses=["INSTALLED"], timeout=60):
            self.setup_failures.append("Probes did not reach INSTALLED status")
            return

        # Telemetry metrics are flushed periodically, so the scenario's library interface timeout leaves time for the
        # skipped events to be reported.
        self.weblog_responses = [weblog.get("/debugger/log") for _ in range(RATE_LIMIT_BURST_SIZE)]

    def test_events_skipped_rate_limit_probe(self):
        self.assert_setup_ok()
        self.assert_rc_state_not_error()
        self.assert_all_weblog_responses_ok()

        legacy_metrics = {
            namespace: sorted({series["metric"] for series in _get_metric_series(namespace)})
            for namespace in LEGACY_DEBUGGER_METRICS_NAMESPACES
        }
        legacy_metrics = {namespace: metrics for namespace, metrics in legacy_metrics.items() if metrics}
        assert not legacy_metrics, (
            f"Debugger metrics must be sent in the {DEBUGGER_METRICS_NAMESPACE!r} namespace, got {legacy_metrics}"
        )

        skips = _get_rate_limit_probe_skips()
        assert skips, (
            f"No events.skipped metric tagged reason:rateLimitProbe in the {DEBUGGER_METRICS_NAMESPACE!r} namespace, "
            f"even though the probe was hit {RATE_LIMIT_BURST_SIZE} times in a row"
        )
        for series in skips:
            assert series["type"] == "count", f"events.skipped must be a count metric, got {series['type']!r}"
        assert sum(point[1] for series in skips for point in series["points"]) > 0
