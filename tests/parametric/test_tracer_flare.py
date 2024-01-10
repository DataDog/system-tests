"""
Test the tracer flare feature of the APM libraries.
"""
import json
import zipfile
from base64 import b64decode
from io import BytesIO
from typing import Any
from typing import Dict
from uuid import uuid4

import pytest

from utils import rfc, scenarios, features

parametrize = pytest.mark.parametrize

TEST_SERVICE = "test_service"
TEST_ENV = "test_env"
DEFAULT_ENVVARS = {
    "DD_SERVICE": TEST_SERVICE,
    "DD_ENV": TEST_ENV,
    # Needed for .NET until Telemetry V2 is released
    "DD_INTERNAL_TELEMETRY_V2_ENABLED": "1",
    # Decrease the heartbeat/poll intervals to speed up the tests
    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.2",
    "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
}


def _tracer_flare_task_config() -> Dict[str, Any]:
    return {
        "args": {
            "case_id": "12345",
            "hostname": "my.hostname",
            "user_handle": "its.me@datadoghq.com",
        },
        "task_type": "tracer_flare",
    }


def _flare_log_level_order() -> Dict[str, Any]:
    return {
        "order": [],
        "internal_order": [
            "flare-log-level.trace",
            "flare-log-level.debug",
            "flare-log-level.info",
            "flare-log-level.warn",
            "flare-log-level.error",
            "flare-log-level.critical",
            "flare-log-level.off",
        ],
    }


def _set_log_level(test_agent, log_level: str) -> None:
    """Helper to create the appropriate "flare-log-level" config in RC for a given log-level.
    """
    cfg_id = f"flare-log-level.{log_level}"
    test_agent.set_remote_config(
        path=f"datadog/2/AGENT_CONFIG/{cfg_id}/config",
        payload={"name": cfg_id, "config": {"log_level": log_level}},
    )
    test_agent.wait_for_rc_apply_state("AGENT_CONFIG", state=2)


def _clear_log_level(test_agent, log_level: str) -> None:
    """Helper to clear a previously set "flare-log-level" config from RC.
    """
    cfg_id = f"flare-log-level.{log_level}"
    test_agent.set_remote_config(
        path=f"datadog/2/AGENT_CONFIG/{cfg_id}/config", payload={}
    )
    test_agent.wait_for_rc_apply_state("AGENT_CONFIG", state=2, clear=True)


def _add_task(test_agent, task_config: Dict[str, Any]) -> int:
    """Helper to create an agent task in RC with the given task arguments.
    """
    task_config["uuid"] = uuid4().hex
    task_id = hash(json.dumps(task_config))
    test_agent.set_remote_config(
        path=f"datadog/2/AGENT_TASK/{task_id}/config", payload=task_config
    )
    test_agent.wait_for_rc_apply_state("AGENT_TASK", state=2)
    return task_id


def _clear_task(test_agent, task_id) -> None:
    """Helper to clear a previously created agent task config from RC.
    """
    test_agent.set_remote_config(
        path=f"datadog/2/AGENT_TASK/{task_id}/config", payload={}
    )
    test_agent.wait_for_rc_apply_state("AGENT_TASK", state=2, clear=True)


def trigger_tracer_flare_and_wait(test_agent, task_overrides: Dict[str, Any]) -> Dict:
    """Creates a "trace_flare" agent task and waits for the tracer flare to be uploaded.
    """
    task_config = _tracer_flare_task_config()
    task_args = task_config["args"]
    for k, v in task_overrides.items():
        task_args[k] = v

    task_id = _add_task(test_agent, task_config)
    tracer_flare = test_agent.wait_for_tracer_flare(task_args["case_id"], clear=True)
    _clear_task(test_agent, task_id)

    return tracer_flare


def assert_valid_zip(content):
    flare_file = zipfile.ZipFile(BytesIO(b64decode(content)))
    assert flare_file.testzip() is None, "tracer_file zip must not contain errors"
    assert flare_file.namelist(), "tracer_file zip must contain at least one entry"


@rfc("https://docs.google.com/document/d/1U9aaYM401mJPTM8YMVvym1zaBxFtS4TjbdpZxhX3c3E")
@scenarios.parametric
@features.tracer_flare
class TestTracerFlareV1:
    @parametrize("library_env", [{"DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1"}])
    def test_telemetry_app_started(self, library_env, test_agent, test_library):
        events = test_agent.wait_for_telemetry_event("app-started")
        assert len(events) > 0

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_flare_log_level_order(self, library_env, test_agent, test_library):
        test_agent.set_remote_config(
            path="datadog/2/AGENT_CONFIG/configuration_order/config",
            payload=_flare_log_level_order(),
        )
        test_agent.wait_for_rc_apply_state("AGENT_CONFIG", state=2)

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_tracer_flare(self, library_env, test_agent, test_library):
        tracer_flare = trigger_tracer_flare_and_wait(test_agent, {})

        assert_valid_zip(tracer_flare["flare_file"])

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_tracer_flare_with_debug(self, library_env, test_agent, test_library):
        _set_log_level(test_agent, "debug")

        tracer_flare = trigger_tracer_flare_and_wait(
            test_agent, {"case_id": "12345-with-debug"}
        )

        _clear_log_level(test_agent, "debug")

        assert_valid_zip(tracer_flare["flare_file"])

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_no_tracer_flare_for_other_task_types(
        self, library_env, test_agent, test_library
    ):
        task_config = {
            "args": {
                "case_id": "12345",
                "hostname": "my.hostname",
                "user_handle": "its.me@datadoghq.com",
            },
            "task_type": "flare",  # this task_type is used to trigger the agent's own flare
        }

        task_id = _add_task(test_agent, task_config)

        try:
            tracer_flare = test_agent.wait_for_tracer_flare(clear=True)
            pytest.fail(f"Expected no tracer flare but got {tracer_flare}")
        except AssertionError as e:
            if str(e) != "No tracer-flare received":
                raise
        finally:
            _clear_task(test_agent, task_id)
