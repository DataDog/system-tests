import json
import os
import time

from utils import pytest

from tests.parametric.conftest import APMLibrary
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI

from .utils import BLRP_LIBRARY_ENV

TARGET = "OTEL_BLRP_MAX_EXPORT_BATCH_SIZE"
ATTEMPTS = range(int(os.environ.get("REPRO_ATTEMPTS", "1")))


def _messages(events: list[dict]) -> list[dict]:
    out = []
    for event in events:
        batch = event.get("payload", []) if event.get("request_type") == "message-batch" else [event]
        for message in batch:
            app = message.get("application") or event.get("application") or {}
            out.append(
                {"request_type": message.get("request_type"), "sidecar": app.get("language_version") == "SIDECAR"}
            )
    return out


def _has_configuration_change(events: list[dict]) -> bool:
    return any(m["request_type"] == "app-client-configuration-change" and not m["sidecar"] for m in _messages(events))


def _record(kind: str, attempt: int, early: list[dict], configurations: dict) -> None:
    path = os.environ.get("REPRO_OUT")
    if path:
        record = {"kind": kind, "attempt": attempt, "early": _messages(early), "returned_names": len(configurations)}
        with open(path, "a", encoding="utf-8") as output:
            output.write(json.dumps(record) + "\n")


def _wait_for_early_event(test_agent: TestAgentAPI) -> list[dict]:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        events = test_agent.telemetry(clear=False)
        if events:
            if _has_configuration_change(events):
                pytest.skip("configuration arrived with the first telemetry request; window not observed")
            return events
        time.sleep(0.002)
    raise AssertionError("no telemetry received")


@scenarios.parametric
@features.otel_blrp_max_export_batch_size
class Test_BLRP_Telemetry_Wait_Repro:
    @pytest.mark.parametrize("attempt", ATTEMPTS)
    @pytest.mark.parametrize("library_env", [{**BLRP_LIBRARY_ENV}])
    def test_repro_wait_returns_before_configuration(
        self, test_agent: TestAgentAPI, test_library: APMLibrary, attempt: int
    ) -> None:
        with test_library:
            early = _wait_for_early_event(test_agent)
            configurations = test_agent.wait_for_telemetry_configurations()
            _record("repro", attempt, early, configurations)
            entries = configurations.get(TARGET)
        assert entries, f"No telemetry configuration '{TARGET}'"

    @pytest.mark.parametrize("attempt", ATTEMPTS)
    @pytest.mark.parametrize("library_env", [{**BLRP_LIBRARY_ENV}])
    def test_control_wait_for_configuration_change(
        self, test_agent: TestAgentAPI, test_library: APMLibrary, attempt: int
    ) -> None:
        with test_library:
            early = _wait_for_early_event(test_agent)
            test_agent.wait_for_telemetry_event("app-client-configuration-change")
            configurations = test_agent.wait_for_telemetry_configurations()
            _record("control", attempt, early, configurations)
            entries = configurations.get(TARGET)
        assert entries, f"No telemetry configuration '{TARGET}'"
