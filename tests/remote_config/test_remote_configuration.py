# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json
from collections import defaultdict

from utils import (
    ValidationError,
    scenario,
    context,
    coverage,
    interfaces,
    missing_feature,
    released,
    rfc,
    bug,
    irrelevant,
)
from utils.tools import logger

with open("tests/remote_config/rc_expected_requests_live_debugging.json", encoding="utf-8") as f:
    LIVE_DEBUGGING_EXPECTED_REQUESTS = json.load(f)

with open("tests/remote_config/rc_expected_requests_asm_features.json", encoding="utf-8") as f:
    ASM_FEATURES_EXPECTED_REQUESTS = json.load(f)

with open("tests/remote_config/rc_expected_requests_asm_dd.json", encoding="utf-8") as f:
    ASM_DD_EXPECTED_REQUESTS = json.load(f)


@rfc("https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph")
class RemoteConfigurationFieldsBasicTests:
    """ Misc tests on fields and values on remote configuration requests """

    def test_schemas(self):
        """ Test all library schemas """
        interfaces.library.assert_schemas()

    def test_client_state_errors(self):
        """ Ensure that the Client State error is consistent """

        def validator(data):
            state = data["request"]["content"]["client"]["state"]

            if state.get("has_error") is True:
                assert (
                    "error" in state
                ), "'client.state.error' must be non-empty if a client reports an error with 'client.state.has_error'"

        interfaces.library.validate_remote_configuration(validator=validator, success_by_default=True)

    def test_client_fields(self):
        """ Ensure that the Client field is appropriately filled out in update requests"""

        def validator(data):
            client = data["request"]["content"]["client"]
            client_tracer = client["client_tracer"]

            assert "is_agent" not in client, "'client.is_agent' MUST either NOT be set or set to false"
            assert "client_agent" not in client, "'client.client_agent' must NOT be set"
            assert (
                client["id"] != client_tracer["runtime_id"]
            ), "'client.id' and 'client.client_tracer.runtime_id' must be distinct"

        interfaces.library.validate_remote_configuration(validator=validator, success_by_default=True)


def rc_check_request(data, expected, caching):
    content = data["request"]["content"]
    client_state = content["client"]["state"]

    # verify that the tracer properly updated the TUF targets version,
    # if it's not included we assume it to be 0 in the agent.
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

    if expected_config_states is not None and config_states is None:
        raise Exception("client is expected to have stored confis but isn't reporting any")

    if config_states is not None:
        assert len(config_states) == len(expected_config_states), "client reporting more or less configs than expected"
        for state in expected_config_states:
            if state not in config_states:
                raise ValidationError(f"Config {state} should be in config_states property", extra_info=content)

    if not caching:
        # if a tracer decides to not cache target files, they are not supposed to fill out cached_target_files
        assert not content.get(
            "cached_target_files", []
        ), "tracers not opting into caching target files must NOT populate cached_target_files in requests"
    else:
        expected_cached_target_files = expected.get("cached_target_files")
        cached_target_files = content.get("cached_target_files")

        if expected_cached_target_files is None and cached_target_files is not None and len(cached_target_files) != 0:
            raise Exception(
                f"client is not expected to have cached config but is reporting cached config: {cached_target_files}"
            )

        if expected_cached_target_files is not None and cached_target_files is None:
            raise Exception(
                "client is expected to have cached config but did not include the cached_target_files field"
            )

        if expected_cached_target_files is not None:
            # Make sure the client reported all of the expected files
            for file in expected_cached_target_files:
                if file not in cached_target_files:
                    raise ValidationError(
                        f"{file} should be in cached_target_files property: {cached_target_files}", extra_info=content
                    )

            # Make sure the client isn't reporting any extra cached files
            for file in cached_target_files:
                if file not in expected_cached_target_files:
                    raise ValidationError(f"{file} should not be in cached_target_files", extra_info=content)


@rfc("https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph")
@released(
    cpp="?", dotnet="2.15.0", golang="?", java="0.115.0", php="?", python="1.7.0rc1.dev", ruby="?", nodejs="3.9.0"
)
@bug(library="dotnet")
@coverage.basic
@scenario("REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES")
class Test_RemoteConfigurationUpdateSequenceFeatures(RemoteConfigurationFieldsBasicTests):
    """Tests that over a sequence of related updates, tracers follow the RFC for the Features product"""

    request_number = 0

    def setup_tracer_update_sequence(self):
        if context.library == "nodejs":
            # time out for nodejs is very low (5 seconds)
            # we need a longer timeout for this test
            interfaces.library.timeout = 120

    @bug(context.weblog_variant == "spring-boot-openliberty", reason="APPSEC-6721")
    @bug(context.library >= "java@1.1.0", reason="?")
    def test_tracer_update_sequence(self):
        """ test update sequence, based on a scenario mocked in the proxy """

        def validate(data):
            """ Helper to validate config request content """
            logger.info(f"validating request number {self.request_number}")
            if self.request_number >= len(ASM_FEATURES_EXPECTED_REQUESTS):
                return True

            rc_check_request(data, ASM_FEATURES_EXPECTED_REQUESTS[self.request_number], caching=True)

            self.request_number += 1

            return False

        interfaces.library.validate_remote_configuration(validator=validate)


@rfc("https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph")
@released(cpp="?", dotnet="2.15.0", golang="?", java="0.113.0", php="?", python="?", ruby="?", nodejs="?")
@coverage.basic
@scenario("REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING")
class Test_RemoteConfigurationUpdateSequenceLiveDebugging(RemoteConfigurationFieldsBasicTests):
    """Tests that over a sequence of related updates, tracers follow the RFC for the Live Debugging product"""

    # Index the request number by runtime ID so that we can support applications
    # that spawns multiple worker processes, each running its own RCM client.
    request_number = defaultdict(int)

    def test_tracer_update_sequence(self):
        """ test update sequence, based on a scenario mocked in the proxy """

        def validate(data):
            """ Helper to validate config request content """
            runtime_id = data["request"]["content"]["client"]["client_tracer"]["runtime_id"]
            logger.info(f"validating request number {self.request_number[runtime_id]}")
            if self.request_number[runtime_id] >= len(LIVE_DEBUGGING_EXPECTED_REQUESTS):
                return True

            rc_check_request(data, LIVE_DEBUGGING_EXPECTED_REQUESTS[self.request_number[runtime_id]], caching=True)

            self.request_number[runtime_id] += 1

            return False

        interfaces.library.validate_remote_configuration(validator=validate)


@rfc("https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph")
@released(cpp="?", dotnet="2.15.0", golang="?", java="0.115.0", php="?", python="?", ruby="?", nodejs="?")
@bug(library="dotnet")
@coverage.basic
@scenario("REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD")
class Test_RemoteConfigurationUpdateSequenceASMDD(RemoteConfigurationFieldsBasicTests):
    """Tests that over a sequence of related updates, tracers follow the RFC for the ASM DD product"""

    request_number = 0

    @bug(context.library >= "java@1.1.0", reason="?")
    @bug(context.weblog_variant == "spring-boot-openliberty", reason="APPSEC-6721")
    def test_tracer_update_sequence(self):
        """ test update sequence, based on a scenario mocked in the proxy """

        def validate(data):
            """ Helper to validate config request content """
            logger.info(f"validating request number {self.request_number}")
            if self.request_number >= len(ASM_DD_EXPECTED_REQUESTS):
                return True

            rc_check_request(data, ASM_DD_EXPECTED_REQUESTS[self.request_number], caching=True)

            self.request_number += 1

            return False

        interfaces.library.validate_remote_configuration(validator=validate)


@rfc("https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph")
@released(
    cpp="?", golang="?", dotnet="2.15.0", java="0.115.0", php="?", python="1.6.0rc1.dev", ruby="?", nodejs="3.9.0"
)
@bug(library="dotnet")
@bug(weblog_variant="django-poc")
@missing_feature(context.library > "python@1.7.0", reason="RC Cache is implemented in 1.7")
@irrelevant(library="nodejs", reason="cache is implemented")
@coverage.basic
@scenario("REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES_NOCACHE")
class Test_RemoteConfigurationUpdateSequenceFeaturesNoCache(RemoteConfigurationFieldsBasicTests):
    """Tests that over a sequence of related updates, tracers follow the RFC for the Features product"""

    request_number = 0

    @bug(library="java", reason="APPSEC-6720")
    def test_tracer_update_sequence(self):
        """ test update sequence, based on a scenario mocked in the proxy """

        def validate(data):
            """ Helper to validate config request content """
            logger.info(f"validating request number {self.request_number}")
            if self.request_number >= len(ASM_FEATURES_EXPECTED_REQUESTS):
                return True

            rc_check_request(data, ASM_FEATURES_EXPECTED_REQUESTS[self.request_number], caching=False)

            self.request_number += 1

            return False

        interfaces.library.validate_remote_configuration(validator=validate)


@rfc("https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph")
@released(cpp="?", dotnet="2.15.0", golang="?", java="0.115.0", php="?", python="?", ruby="?", nodejs="?")
@bug(library="dotnet")
@coverage.basic
@scenario("REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING_NOCACHE")
class Test_RemoteConfigurationUpdateSequenceLiveDebuggingNoCache(RemoteConfigurationFieldsBasicTests):
    """Tests that over a sequence of related updates, tracers follow the RFC for the Live Debugging product"""

    request_number = defaultdict(int)

    @bug(library="java", reason="APPSEC-6720")
    def test_tracer_update_sequence(self):
        """ test update sequence, based on a scenario mocked in the proxy """

        def validate(data):
            """ Helper to validate config request content """
            runtime_id = data["request"]["content"]["client"]["client_tracer"]["runtime_id"]
            logger.info(f"validating request number {self.request_number[runtime_id]}")
            if self.request_number[runtime_id] >= len(LIVE_DEBUGGING_EXPECTED_REQUESTS):
                return True

            rc_check_request(data, LIVE_DEBUGGING_EXPECTED_REQUESTS[self.request_number[runtime_id]], caching=False)

            self.request_number[runtime_id] += 1

            return False

        interfaces.library.validate_remote_configuration(validator=validate)


@rfc("https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph")
@released(cpp="?", dotnet="2.15.0", golang="?", java="0.115.0", php="?", python="?", ruby="?", nodejs="?")
@bug(library="dotnet")
@coverage.basic
@scenario("REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD_NOCACHE")
class Test_RemoteConfigurationUpdateSequenceASMDDNoCache(RemoteConfigurationFieldsBasicTests):
    """Tests that over a sequence of related updates, tracers follow the RFC for the ASM DD product"""

    request_number = 0

    @bug(library="java", reason="APPSEC-6720")
    def test_tracer_update_sequence(self):
        """ test update sequence, based on a scenario mocked in the proxy """

        def validate(data):
            """ Helper to validate config request content """
            logger.info(f"validating request number {self.request_number}")
            if self.request_number >= len(ASM_DD_EXPECTED_REQUESTS):
                return True

            rc_check_request(data, ASM_DD_EXPECTED_REQUESTS[self.request_number], caching=False)

            self.request_number += 1

            return False

        interfaces.library.validate_remote_configuration(validator=validate)
