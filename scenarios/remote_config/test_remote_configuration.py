# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, interfaces, released, rfc, coverage, proxies, context
from utils.tools import logger
import json

with open("scenarios/remote_config/rc_expected_requests_live_debugging.json") as f:
    LIVE_DEBUGGING_EXPECTED_REQUESTS = json.load(f)

with open("scenarios/remote_config/rc_expected_requests_features.json") as f:
    FEATURES_EXPECTED_REQUESTS = json.load(f)

with open("scenarios/remote_config/rc_expected_requests_asm_dd.json") as f:
    ASM_DD_EXPECTED_REQUESTS = json.load(f)


@rfc("https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph")
@released(cpp="?", dotnet="?", java="?", php="?", python="?", ruby="?", nodejs="?")
@coverage.basic
class Test_RemoteConfigurationFields(BaseTestCase):
    """ Misc tests on fields and values on remote configuration reauests """

    def test_shemas(self):
        interfaces.library.assert_schemas()

    def test_tracer_language(self):
        """ Ensure that tracer clients use the correct word for the language """

        def validator(data):
            content = data["request"]["content"]
            assert "client" in content, f"'client' is missing in {data['log_filename']}"
            assert "client_tracer" in content["client"], f"'client_tracer' is missing in {data['log_filename']}"

            language = data["request"]["content"]["client"]["client_tracer"].get("language")

            expected_language = {
                "cpp": "cpp",
                "dotnet": "dotnet",
                "golang": "go",
                "nodejs": "node",
                "java": "java",
                "php": "php",
                "python": "python",
                "ruby": "ruby",
            }[context.library.library]

            assert language == expected_language, f"language is '{language}', I was expecting '{expected_language}'"

        interfaces.library.add_remote_configuration_validation(validator=validator, is_success_on_expiry=True)

    def test_client_state_errors(self):
        """ Ensure that the Client State error is consistent """

        def validator(data):
            content = data["request"]["content"]
            state = content.get("client", {}).get("state", {})

            if "has_error" in state and state["has_error"] == True:
                assert (
                    "error" in state and state["error"] != ""
                ), f"'client.state.error' must be non-empty if a client reports an error with 'client.state.has_error'"

        interfaces.library.add_remote_configuration_validation(validator=validator, is_success_on_expiry=True)

    def test_client_fields(self):
        """ Ensure that the Client field is appropriately filled out in update requests"""

        def validator(data):
            content = data["request"]["content"]
            client = content.get("client", {})

            assert "is_agent" not in client, f"'client.is_agent' MUST either NOT be set or set to false"
            assert "client_agent" not in client, f"'client.client_agent' must NOT be set"

            client_tracer = client.get("client_tracer", {})
            assert (
                client["id"] != client_tracer["runtime_id"]
            ), f"'client.id' and 'client.client_tracer.runtime_id' must be distinct"

        interfaces.library.add_remote_configuration_validation(validator=validator, is_success_on_expiry=True)


def rc_check_request(data, expected, caching):
    content = data["request"]["content"]
    client_state = content["client"]["state"]

    # verify that the tracer properly updated the TUF targets version, if it's not included we assume it to be 0 in the agent.
    # Our test suite will always emit SOMETHING for this
    expected_targets_version = expected["client"]["state"]["targets_version"]
    targets_version = client_state.get("targets_version", 0)
    assert (
        targets_version == expected_targets_version
    ), f"targetsVersion was expected to be {expected_targets_version}, not {targets_version}"

    # verify that the tracer is properly storing and reporting on its config state
    expected_config_states = client_state.get("config_states")
    config_states = client_state.get("config_states")
    if expected_config_states is None and config_states is not None:
        raise Exception("client is not expected to have stored config but is reporting stored configs")
    elif expected_config_states is not None and config_states is None:
        raise Exception("client is expected to have stored confis but isn't reporting any")
    elif config_states is not None:
        assert len(config_states) == len(expected_config_states), "client reporting more or less configs than expected"
        for state in expected_config_states:
            assert state in config_states, f"{state} is not in {config_states}"

    if not caching:
        # if a tracer decides to not cache target files, they are not supposed to fill out cached_target_files
        assert (
            "cached_target_files" not in expected or len(expected["cached_target_files"]) == 0
        ), "tracers not opting into caching target files must NOT populate cached_target_files in requests"
    else:
        expected_cached_target_files = expected.get("cached_target_files")
        cached_target_files = content.get("cached_target_files")

        if expected_cached_target_files is None and cached_target_files is not None and len(cached_target_files) != 0:
            raise Exception("client is not expected to have cached config but is reporting cached config")
        elif expected_cached_target_files is not None and cached_target_files is None:
            raise Exception(
                "client is expected to have cached config but did not include the cached_target_files field"
            )
        elif expected_cached_target_files is not None:
            # Make sure the client reported all of the expected files
            for file in expected_cached_target_files:
                assert file in cached_target_files, f"{file} is not in {cached_target_files}"
            # Make sure the client isn't reporting any extra cached files
            for file in cached_target_files:
                assert file in expected_cached_target_files, f"unepxected file {file} in cached_target_files"


@rfc("https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph")
@released(cpp="?", dotnet="?", java="?", php="?", python="?", ruby="?", nodejs="?")
@coverage.basic
class Test_RemoteConfigurationUpdateSequenceFeatures(BaseTestCase):
    """Tests that over a sequence of related updates, tracers follow the RFC for the Features product"""

    request_number = 0

    def test_tracer_update_sequence(self):
        """ test update sequence, based on a scenario mocked in the proxy """

        def validate(data):
            """ Helper to validate config request content """
            logger.info(f"validating request number {self.request_number}")
            if self.request_number >= len(FEATURES_EXPECTED_REQUESTS):
                return True

            rc_check_request(data, FEATURES_EXPECTED_REQUESTS[self.request_number], caching=True)

            self.request_number += 1

        interfaces.library.add_remote_configuration_validation(validator=validate)


@rfc("https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph")
@released(cpp="?", dotnet="?", java="?", php="?", python="?", ruby="?", nodejs="?")
@coverage.basic
class Test_RemoteConfigurationUpdateSequenceLiveDebugging(BaseTestCase):
    """Tests that over a sequence of related updates, tracers follow the RFC for the Live Debugging product"""

    request_number = 0

    def test_tracer_update_sequence(self):
        """ test update sequence, based on a scenario mocked in the proxy """

        def validate(data):
            """ Helper to validate config request content """
            logger.info(f"validating request number {self.request_number}")
            if self.request_number >= len(LIVE_DEBUGGING_EXPECTED_REQUESTS):
                return True

            rc_check_request(data, LIVE_DEBUGGING_EXPECTED_REQUESTS[self.request_number], caching=True)

            self.request_number += 1

        interfaces.library.add_remote_configuration_validation(validator=validate)


@rfc("https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph")
@released(cpp="?", dotnet="?", java="?", php="?", python="?", ruby="?", nodejs="?")
@coverage.basic
class Test_RemoteConfigurationUpdateSequenceASMDD(BaseTestCase):
    """Tests that over a sequence of related updates, tracers follow the RFC for the ASM DD product"""

    request_number = 0

    def test_tracer_update_sequence(self):
        """ test update sequence, based on a scenario mocked in the proxy """

        def validate(data):
            """ Helper to validate config request content """
            logger.info(f"validating request number {self.request_number}")
            if self.request_number >= len(ASM_DD_EXPECTED_REQUESTS):
                return True

            rc_check_request(data, ASM_DD_EXPECTED_REQUESTS[self.request_number], caching=True)

            self.request_number += 1

        interfaces.library.add_remote_configuration_validation(validator=validate)


@rfc("https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph")
@released(cpp="?", dotnet="?", java="?", php="?", python="?", ruby="?", nodejs="?")
@coverage.basic
class Test_RemoteConfigurationUpdateSequenceFeaturesNoCache(BaseTestCase):
    """Tests that over a sequence of related updates, tracers follow the RFC for the Features product"""

    request_number = 0

    def test_tracer_update_sequence(self):
        """ test update sequence, based on a scenario mocked in the proxy """

        def validate(data):
            """ Helper to validate config request content """
            logger.info(f"validating request number {self.request_number}")
            if self.request_number >= len(FEATURES_EXPECTED_REQUESTS):
                return True

            rc_check_request(data, FEATURES_EXPECTED_REQUESTS[self.request_number], caching=False)

            self.request_number += 1

        interfaces.library.add_remote_configuration_validation(validator=validate)


@rfc("https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph")
@released(cpp="?", dotnet="?", java="?", php="?", python="?", ruby="?", nodejs="?")
@coverage.basic
class Test_RemoteConfigurationUpdateSequenceLiveDebuggingNoCache(BaseTestCase):
    """Tests that over a sequence of related updates, tracers follow the RFC for the Live Debugging product"""

    request_number = 0

    def test_tracer_update_sequence(self):
        """ test update sequence, based on a scenario mocked in the proxy """

        def validate(data):
            """ Helper to validate config request content """
            logger.info(f"validating request number {self.request_number}")
            if self.request_number >= len(LIVE_DEBUGGING_EXPECTED_REQUESTS):
                return True

            rc_check_request(data, LIVE_DEBUGGING_EXPECTED_REQUESTS[self.request_number], caching=False)

            self.request_number += 1

        interfaces.library.add_remote_configuration_validation(validator=validate)


@rfc("https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph")
@released(cpp="?", dotnet="?", java="?", php="?", python="?", ruby="?", nodejs="?")
@coverage.basic
class Test_RemoteConfigurationUpdateSequenceASMDDNoCache(BaseTestCase):
    """Tests that over a sequence of related updates, tracers follow the RFC for the ASM DD product"""

    request_number = 0

    def test_tracer_update_sequence(self):
        """ test update sequence, based on a scenario mocked in the proxy """

        def validate(data):
            """ Helper to validate config request content """
            logger.info(f"validating request number {self.request_number}")
            if self.request_number >= len(ASM_DD_EXPECTED_REQUESTS):
                return True

            rc_check_request(data, ASM_DD_EXPECTED_REQUESTS[self.request_number], caching=False)

            self.request_number += 1

        interfaces.library.add_remote_configuration_validation(validator=validate)
