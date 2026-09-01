import base64
import json

from utils import remote_config as rc, scenarios
from utils.dd_constants import Capabilities


@scenarios.test_the_test
def test_debugger_command_none():
    expected = {
        "targets": "ewogICJzaWduYXR1cmVzIjogWwogICAgewogICAgICAia2V5aWQiOiAiMTM5ZTM5NDBlNjRiNTQ5MTcyMjA4OGQ5YTBkNzQxNjI4ZmM4MjZlMDk0NzVkMzQxYTc4MGFjZGUzYzRiODA3MCIsCiAgICAgICJzaWciOiAiNWIyNDJlMDg5MjI0ZWExMzg5MjU0ZGE4MGQxMWQ3MWM4MDNkMGMyMGE1NDg1NzgwMGE2OTM4OWRhZjJlMjQwZTcyNTQ0Mjk0MjAzZWEyZWFmMDdmZjIzNjMxMzJjOGYxYWFmZTg4MTY0MTAwNWIwYzYwNjgwM2M4MWQzMzBiMGQiCiAgICB9CiAgXSwKICAic2lnbmVkIjogewogICAgIl90eXBlIjogInRhcmdldHMiLAogICAgImN1c3RvbSI6IHsKICAgICAgIm9wYXF1ZV9iYWNrZW5kX3N0YXRlIjogImV5Sm1iMjhpT2lBaVltRnlJbjA9IgogICAgfSwKICAgICJleHBpcmVzIjogIjMwMDAtMDEtMDFUMDA6MDA6MDBaIiwKICAgICJzcGVjX3ZlcnNpb24iOiAiMS4wIiwKICAgICJ0YXJnZXRzIjoge30sCiAgICAidmVyc2lvbiI6IDAKICB9Cn0=",
        "target_files": [],
        "client_configs": [],
    }

    obeserved = rc.build_debugger_command(None, 0)

    assert obeserved == expected


@scenarios.test_the_test
def test_debugger_command_one_probe():
    probes = [
        {
            "language": "",
            "id": "log170aa-acda-4453-9111-1478a6method",
            "type": "LOG_PROBE",
            "where": {"typeName": "ACTUAL_TYPE_NAME", "methodName": "Pii", "sourceFile": None},
            "evaluateAt": "EXIT",
            "captureSnapshot": True,
            "capture": {"maxFieldCount": 200},
        }
    ]

    expected = {
        "targets": "ewogICJzaWduYXR1cmVzIjogWwogICAgewogICAgICAia2V5aWQiOiAiMTM5ZTM5NDBlNjRiNTQ5MTcyMjA4OGQ5YTBkNzQxNjI4ZmM4MjZlMDk0NzVkMzQxYTc4MGFjZGUzYzRiODA3MCIsCiAgICAgICJzaWciOiAiZjk0NzliYTAyNDRkYjBlMDAxNjdiZjczNTE0NTQxMWZmOTk3MmU2NWI0Njc5NzllODZjNDRiZmNhZmQ2OGEyNjQ4YzcyOGVkMDEwOTZhNDg4YmQ3ZWJjYTMyZTUzMWNjODdiYjBkYWYxMDA2YWQxODRjNTQ4OTQyN2Q5Nzc4MDMiCiAgICB9CiAgXSwKICAic2lnbmVkIjogewogICAgIl90eXBlIjogInRhcmdldHMiLAogICAgImN1c3RvbSI6IHsKICAgICAgIm9wYXF1ZV9iYWNrZW5kX3N0YXRlIjogImV5Sm1iMjhpT2lBaVltRnlJbjA9IgogICAgfSwKICAgICJleHBpcmVzIjogIjMwMDAtMDEtMDFUMDA6MDA6MDBaIiwKICAgICJzcGVjX3ZlcnNpb24iOiAiMS4wIiwKICAgICJ0YXJnZXRzIjogewogICAgICAiZGF0YWRvZy8yL0xJVkVfREVCVUdHSU5HL2xvZ1Byb2JlX2xvZzE3MGFhLWFjZGEtNDQ1My05MTExLTE0NzhhNm1ldGhvZC9jb25maWciOiB7CiAgICAgICAgImN1c3RvbSI6IHsKICAgICAgICAgICJ2IjogMQogICAgICAgIH0sCiAgICAgICAgImhhc2hlcyI6IHsKICAgICAgICAgICJzaGEyNTYiOiAiZWNmMzQ3ZmIwZWE0NjE2ZmU1NTc2YzIyODNhYWY1NmUyNjFmYmNjZDMxNjJiYTIxZjNjZmQwNDJjM2VjOWFjNSIKICAgICAgICB9LAogICAgICAgICJsZW5ndGgiOiAyODkKICAgICAgfQogICAgfSwKICAgICJ2ZXJzaW9uIjogMQogIH0KfQ==",
        "target_files": [
            {
                "path": "datadog/2/LIVE_DEBUGGING/logProbe_log170aa-acda-4453-9111-1478a6method/config",
                "raw": "ewogICJsYW5ndWFnZSI6ICIiLAogICJpZCI6ICJsb2cxNzBhYS1hY2RhLTQ0NTMtOTExMS0xNDc4YTZtZXRob2QiLAogICJ0eXBlIjogIkxPR19QUk9CRSIsCiAgIndoZXJlIjogewogICAgInR5cGVOYW1lIjogIkFDVFVBTF9UWVBFX05BTUUiLAogICAgIm1ldGhvZE5hbWUiOiAiUGlpIiwKICAgICJzb3VyY2VGaWxlIjogbnVsbAogIH0sCiAgImV2YWx1YXRlQXQiOiAiRVhJVCIsCiAgImNhcHR1cmVTbmFwc2hvdCI6IHRydWUsCiAgImNhcHR1cmUiOiB7CiAgICAibWF4RmllbGRDb3VudCI6IDIwMAogIH0KfQ==",
            }
        ],
        "client_configs": ["datadog/2/LIVE_DEBUGGING/logProbe_log170aa-acda-4453-9111-1478a6method/config"],
    }

    obeserved = rc.build_debugger_command(probes, 1)

    assert obeserved == expected


@scenarios.test_the_test
def test_to_sdk_config_payload():
    """The lib_config object is replaced by an env-var-keyed sdk_config, everything else is kept"""
    observed = rc.to_sdk_config_payload(
        {
            "schema_version": "v1.0.0",
            "action": "enable",
            "service_target": {"service": "weblog", "env": "system-tests"},
            "lib_config": {
                "library_language": "all",
                "library_version": "latest",
                "tracing_enabled": True,
                "dynamic_instrumentation_enabled": False,
                "tracing_sampling_rate": 0.5,
                "code_origin_enabled": None,
            },
        }
    )

    assert observed == {
        "schema_version": "v1.0.0",
        "action": "enable",
        "service_target": {"service": "weblog", "env": "system-tests"},
        "sdk_config": {
            "service_name": "weblog",
            "env": "system-tests",
            "config": [
                {"key": "DD_TRACE_ENABLED", "value": "true"},
                {"key": "DD_DYNAMIC_INSTRUMENTATION_ENABLED", "value": "false"},
                {"key": "DD_TRACE_SAMPLE_RATE", "value": "0.5"},
            ],
        },
    }


@scenarios.test_the_test
def test_to_sdk_config_payload_complex_values():
    """Settings that are objects in lib_config are serialized to their environment variable form"""
    observed = rc.to_sdk_config_payload(
        {
            "service_target": {"service": "*", "env": "*"},
            "lib_config": {
                "tracing_header_tags": [
                    {"header": "X-Test-Header", "tag_name": "test_header_rc"},
                    {"header": "Content-Length", "tag_name": ""},
                ],
                "tracing_tags": ["rc_key1:val1", "rc_key2:val2"],
                "tracing_service_mapping": [{"from_key": "inbound", "to_name": "outbound"}],
                "tracing_sampling_rules": [
                    {
                        "sample_rate": 0.8,
                        "service": "test_service",
                        "resource": "*",
                        "tags": [{"key": "tag-a", "value_glob": "tag-a-val*"}],
                        "provenance": "customer",
                    }
                ],
            },
        }
    )

    assert observed["sdk_config"]["config"] == [
        {"key": "DD_TRACE_HEADER_TAGS", "value": "X-Test-Header:test_header_rc,Content-Length"},
        {"key": "DD_TAGS", "value": "rc_key1:val1,rc_key2:val2"},
        {"key": "DD_SERVICE_MAPPING", "value": "inbound:outbound"},
        {
            "key": "DD_TRACE_SAMPLING_RULES",
            # the list of tag clauses becomes the map the environment variable expects
            "value": (
                '[{"sample_rate": 0.8, "service": "test_service", "resource": "*", '
                '"tags": {"tag-a": "tag-a-val*"}, "provenance": "customer"}]'
            ),
        },
    ]


@scenarios.test_the_test
def test_to_sdk_config_payload_drops_remote_only_settings():
    """Settings without an environment variable counterpart can't be expressed as sdk_config"""
    observed = rc.to_sdk_config_payload(
        {
            "service_target": {"service": "weblog", "env": "system-tests"},
            "lib_config": {
                "dynamic_sampling_enabled": "true",
                "live_debugging_enabled": True,
                "not_a_known_setting": True,
                "exception_replay_enabled": True,
            },
        }
    )

    assert observed["sdk_config"]["config"] == [{"key": "DD_EXCEPTION_REPLAY_ENABLED", "value": "true"}]


@scenarios.test_the_test
def test_to_sdk_config_payload_empty_lib_config():
    """An empty config resets every remotely set value, and stays empty once translated"""
    observed = rc.to_sdk_config_payload({"action": "enable", "lib_config": {"tracing_sampling_rate": None}})

    assert observed == {"action": "enable", "sdk_config": {"config": []}}


@scenarios.test_the_test
def test_apm_tracing_command_settings_are_all_mapped():
    """Every setting the APM_TRACING builders can emit must have a known sdk_config translation"""
    _, apm_config = rc.build_combined_apm_tracing_and_debugger_command(
        1,
        [],
        dynamic_instrumentation_enabled=True,
        exception_replay_enabled=True,
        live_debugging_enabled=True,
        code_origin_enabled=True,
        dynamic_sampling_enabled=True,
    )
    unknown = set(apm_config["lib_config"]) - set(rc.APM_TRACING_ENV_VAR_NAMES) - rc._LIB_CONFIG_METADATA_KEYS  # noqa: SLF001

    assert not unknown, f"APM_TRACING_ENV_VAR_NAMES is missing an entry for {unknown}"


@scenarios.test_the_test
def test_build_apm_tracing_command_use_sdk_config():
    """The command carries the sdk_config shape, while prev_payloads keeps the legacy one"""
    prev_payloads: list[dict] = []
    command = rc.build_apm_tracing_command(1, prev_payloads, dynamic_instrumentation_enabled=True, use_sdk_config=True)

    sent = json.loads(base64.b64decode(command["target_files"][0]["raw"]))
    assert "lib_config" not in sent
    assert {"key": "DD_DYNAMIC_INSTRUMENTATION_ENABLED", "value": "true"} in sent["sdk_config"]["config"]

    # the next command inherits its defaults from prev_payloads, which stays in the legacy shape
    assert prev_payloads[-1]["lib_config"]["dynamic_instrumentation_enabled"] is True


@scenarios.test_the_test
def test_build_apm_tracing_command_legacy_by_default():
    """Libraries that do not advertise SDK_CONFIGURATION keep receiving lib_config"""
    command = rc.build_apm_tracing_command(1, [], dynamic_instrumentation_enabled=True)

    sent = json.loads(base64.b64decode(command["target_files"][0]["raw"]))
    assert "sdk_config" not in sent
    assert sent["lib_config"]["dynamic_instrumentation_enabled"] is True


@scenarios.test_the_test
def test_resolve_sdk_configuration_contract():
    """The SDK_CONFIGURATION bit alone does not mean the library reads sdk_config.

    Bit 49 is SDK_CONFIGURATION in the remote config source of truth, but libdatadog gives the
    same bit to ASM_RAW_RESPONSE_BODY, so the per-setting capabilities have to be gone too.
    """
    # dd-trace-js with the SDK_CONFIGURATION support: the per-setting capabilities are dropped
    assert rc.resolve_sdk_configuration_contract(
        {
            Capabilities.ASM_ACTIVATION,
            Capabilities.APM_TRACING_MULTICONFIG,
            Capabilities.SDK_CONFIGURATION,
        }
    )

    # dd-trace-php: bit 49 is ASM_RAW_RESPONSE_BODY there, and lib_config is still what it reads
    assert (
        rc.resolve_sdk_configuration_contract(
            {
                Capabilities.APM_TRACING_CUSTOM_TAGS,
                Capabilities.APM_TRACING_ENABLED,
                Capabilities.APM_TRACING_HTTP_HEADER_TAGS,
                Capabilities.APM_TRACING_LOGS_INJECTION,
                Capabilities.APM_TRACING_SAMPLE_RATE,
                Capabilities.APM_TRACING_SAMPLE_RULES,
                Capabilities.APM_TRACING_MULTICONFIG,
                Capabilities.SDK_CONFIGURATION,
            }
        )
        is False
    )

    # dd-trace-java: no SDK_CONFIGURATION at all
    assert (
        rc.resolve_sdk_configuration_contract({Capabilities.APM_TRACING_SAMPLE_RATE, Capabilities.APM_TRACING_ENABLED})
        is False
    )

    # Only ASM capabilities registered so far: nothing to conclude, ask again later
    assert rc.resolve_sdk_configuration_contract({Capabilities.ASM_ACTIVATION}) is None
    assert rc.resolve_sdk_configuration_contract(set()) is None
