# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json
from collections import defaultdict

from utils import (
    ValidationError,
    bug,
    context,
    interfaces,
    irrelevant,
    missing_feature,
    rfc,
    scenarios,
    weblog,
    features,
    remote_config,
)

from utils.tools import logger

with open("tests/remote_config/rc_expected_requests_live_debugging.json", encoding="utf-8") as f:
    LIVE_DEBUGGING_EXPECTED_REQUESTS = json.load(f)

with open("tests/remote_config/rc_expected_requests_asm_features.json", encoding="utf-8") as f:
    ASM_FEATURES_EXPECTED_REQUESTS = json.load(f)

with open("tests/remote_config/rc_expected_requests_asm_dd.json", encoding="utf-8") as f:
    ASM_DD_EXPECTED_REQUESTS = json.load(f)


@features.agent_remote_configuration
class Test_Agent:
    """misc test on agent/remote config features"""

    @irrelevant(library="nodejs", reason="nodejs tracer does not call /info")
    @missing_feature(library="ruby", reason="ruby tracer does not call /info")
    @irrelevant(library="cpp")
    @scenarios.remote_config_mocked_backend_asm_dd
    def test_agent_provide_config_endpoint(self):
        """Check that agent exposes /v0.7/config endpoint"""
        for data in interfaces.library.get_data("/info"):
            for endpoint in data["response"]["content"]["endpoints"]:
                if endpoint == "/v0.7/config":
                    return

        raise ValueError("Agent did not provide /v0.7/config endpoint")


@rfc("https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph")
@features.remote_config_object_supported
class RemoteConfigurationFieldsBasicTests:
    """Misc tests on fields and values on remote configuration requests"""

    def assert_client_fields(self):
        """Ensure that the Client field is appropriately filled out in update requests"""

        def validator(data):
            client = data["request"]["content"]["client"]
            client_tracer = client["client_tracer"]

            assert (
                "is_agent" not in client or client["is_agent"] is False
            ), "'client.is_agent' MUST either NOT be set or set to false"
            assert "client_agent" not in client, "'client.client_agent' must NOT be set"
            assert (
                client["id"] != client_tracer["runtime_id"]
            ), "'client.id' and 'client.client_tracer.runtime_id' must be distinct"

        interfaces.library.validate_remote_configuration(validator=validator, success_by_default=True)


def dict_is_included(sub_dict: dict, main_dict: dict):
    """returns true if every field/values in sub_dict are in main_dict"""

    for key, value in sub_dict.items():
        if key not in main_dict or value != main_dict[key]:
            return False

    return True


def dict_is_in_array(needle: dict, haystack: list, allow_additional_fields=True):
    """
    returns true is needle is contained in haystack.
    If allow_additional_field is true, needle can contains less field than the one in haystack
    """

    for item in haystack:
        if dict_is_included(needle, item):
            if allow_additional_fields or len(needle) == len(item):
                return True

    return False


def rc_check_request(data, expected, caching):
    content = data["request"]["content"]
    client_state = content["client"]["state"]
    expected_client_state = expected["client"]["state"]

    try:
        # verify that the tracer properly updated the TUF targets version,
        # if it's not included we assume it to be 0 in the agent.
        # Our test suite will always emit SOMETHING for this
        expected_targets_version = expected_client_state.get("targets_version")
        targets_version = client_state.get("targets_version", 0)
        assert (
            targets_version == expected_targets_version
        ), f"targetsVersion was expected to be {expected_targets_version}, not {targets_version}"

        # verify that the tracer is properly storing and reporting on its config state
        expected_config_states = expected_client_state.get("config_states")
        config_states = client_state.get("config_states")

        if expected_config_states is None and (config_states is not None and len(config_states) > 0):
            raise ValidationError(
                "client is not expected to have stored config but is reporting stored configs",
                extra_info={"observed_config_states": config_states},
            )

        if expected_config_states is not None and config_states is None:
            raise ValidationError(
                "client is expected to have stored confis but isn't reporting any",
                extra_info={"expected_config_states": expected_config_states, "observed_client_state": client_state},
            )

        if config_states is not None and expected_config_states is not None:
            assert len(config_states) == len(
                expected_config_states
            ), "client reporting more or less configs than expected"

            for state in expected_config_states:
                if not dict_is_in_array(state, config_states, allow_additional_fields=True):
                    raise ValidationError(
                        "A config state is missing in config_states property",
                        extra_info={"expected_config_state": state, "observed_config_states": config_states},
                    )

        if not caching:
            # if a tracer decides to not cache target files, they are not supposed to fill out cached_target_files
            assert not content.get(
                "cached_target_files", []
            ), "tracers not opting into caching target files must NOT populate cached_target_files in requests"
        else:
            expected_cached_target_files = expected.get("cached_target_files")
            cached_target_files = content.get("cached_target_files")

            if (
                expected_cached_target_files is None
                and cached_target_files is not None
                and len(cached_target_files) != 0
            ):
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
                            f"{file} should be in cached_target_files property: {cached_target_files}",
                            extra_info=content,
                        )

                # Make sure the client isn't reporting any extra cached files
                for file in cached_target_files:
                    if file not in expected_cached_target_files:
                        raise ValidationError(f"{file} should not be in cached_target_files", extra_info=content)
    except Exception as e:
        e.args += (expected.get("test_description", "No description"),)
        raise e


@rfc("https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph")
@scenarios.remote_config_mocked_backend_asm_features
@features.appsec_onboarding
class Test_RemoteConfigurationUpdateSequenceFeatures(RemoteConfigurationFieldsBasicTests):
    """Tests that over a sequence of related updates, tracers follow the RFC for the Features product"""

    request_number = 0
    python_request_number = 0

    @bug(context.library == "python@1.9.2")
    @bug(context.weblog_variant == "spring-boot-openliberty", reason="APPSEC-6721")
    @bug(
        context.library >= "java@1.4.0" and context.agent_version < "1.8.0" and context.appsec_rules_file is not None,
        reason="ASM_FEATURES was not subscribed when a custom rules file was present",
    )
    @bug(library="golang", reason="missing update file datadog/2/ASM_FEATURES/ASM_FEATURES-third/config")
    @bug(context.library < "java@1.13.0", reason="id reported for config state is not the expected one")
    def test_tracer_update_sequence(self):
        """test update sequence, based on a scenario mocked in the proxy"""

        self.assert_client_fields()

        def validate(data):
            """Helper to validate config request content"""
            logger.info(f"validating request number {self.request_number}")
            if self.request_number >= len(ASM_FEATURES_EXPECTED_REQUESTS):
                return True

            rc_check_request(data, ASM_FEATURES_EXPECTED_REQUESTS[self.request_number], caching=True)

            self.python_request_number += 1
            if (
                context.library == "python"
                and str(context.library) < "python@1.14.0rc2"
                and context.weblog_variant != "uwsgi-poc"
            ):
                if self.python_request_number % 2 == 0:
                    self.request_number += 1
            else:
                self.request_number += 1

            return False

        interfaces.library.validate_remote_configuration(validator=validate)


@scenarios.remote_config_mocked_backend_asm_features
@features.remote_config_object_supported
class Test_RemoteConfigurationExtraServices:
    """Tests that extra services are sent in the RC message"""

    def setup_tracer_extra_services(self):
        self.r_outgoing = weblog.get("/createextraservice?serviceName=extraVegetables")

        def remote_config_asm_extra_services_available(data):
            if data["path"] == "/v0.7/config":
                client_tracer = data.get("request", {}).get("content", {}).get("client", {}).get("client_tracer", {})
                if "extra_services" in client_tracer:
                    extra_services = client_tracer["extra_services"]

                    if extra_services is not None and "extraVegetables" in extra_services:
                        return True

                return False

        interfaces.library.wait_for(remote_config_asm_extra_services_available, timeout=30)

    def test_tracer_extra_services(self):
        """Test extra services field"""
        import itertools

        # filter extra services
        extra_services = []
        for data in interfaces.library.get_data():
            if data["path"] == "/v0.7/config":
                client_tracer = data["request"]["content"]["client"]["client_tracer"]
                if "extra_services" in client_tracer:
                    extra_services.append(client_tracer["extra_services"] or [])
        assert self.r_outgoing.status_code == 200
        assert extra_services, "extra_services not found"
        extra_services = list(itertools.dropwhile(lambda es: "extraVegetables" not in es, extra_services))
        assert extra_services, "no extra_services contains extraVegetables"
        assert all(
            "extraVegetables" in es for es in extra_services
        ), "extraVegetables is not found in all requests after it was initially added"


@rfc("https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph")
@scenarios.remote_config_mocked_backend_live_debugging
@features.remote_config_object_supported
class Test_RemoteConfigurationUpdateSequenceLiveDebugging(RemoteConfigurationFieldsBasicTests):
    """Tests that over a sequence of related updates, tracers follow the RFC for the Live Debugging product"""

    # Index the request number by runtime ID so that we can support applications
    # that spawns multiple worker processes, each running its own RCM client.
    request_number = defaultdict(int)

    @bug(context.library < "java@1.13.0", reason="id reported for config state is not the expected one")
    def test_tracer_update_sequence(self):
        """test update sequence, based on a scenario mocked in the proxy"""

        self.assert_client_fields()

        def validate(data):
            """Helper to validate config request content"""
            runtime_id = data["request"]["content"]["client"]["client_tracer"]["runtime_id"]
            logger.info(f"validating request number {self.request_number[runtime_id]}")
            if self.request_number[runtime_id] >= len(LIVE_DEBUGGING_EXPECTED_REQUESTS):
                return True

            rc_check_request(data, LIVE_DEBUGGING_EXPECTED_REQUESTS[self.request_number[runtime_id]], caching=True)

            self.request_number[runtime_id] += 1

            return False

        interfaces.library.validate_remote_configuration(validator=validate)


@rfc("https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph")
@scenarios.remote_config_mocked_backend_asm_dd
@features.remote_config_object_supported
class Test_RemoteConfigurationUpdateSequenceASMDD(RemoteConfigurationFieldsBasicTests):
    """Tests that over a sequence of related updates, tracers follow the RFC for the ASM DD product"""

    request_number = 0

    @bug(context.library >= "java@1.1.0" and context.library < "java@1.4.0", reason="?")
    @irrelevant(
        context.library >= "java@1.4.0" and context.appsec_rules_file is not None,
        reason="ASM_DD not subscribed with custom rules. This is the compliant behavior",
    )
    @bug(context.weblog_variant == "spring-boot-openliberty", reason="APPSEC-6721")
    @bug(context.library <= "java@1.12.1", reason="config state id value was wrong")
    def test_tracer_update_sequence(self):
        """test update sequence, based on a scenario mocked in the proxy"""

        self.assert_client_fields()

        def validate(data):
            """Helper to validate config request content"""
            logger.info(f"validating request number {self.request_number}")
            if self.request_number >= len(ASM_DD_EXPECTED_REQUESTS):
                return True

            rc_check_request(data, ASM_DD_EXPECTED_REQUESTS[self.request_number], caching=True)

            self.request_number += 1

            return False

        interfaces.library.validate_remote_configuration(validator=validate)


@rfc("https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph")
@scenarios.remote_config_mocked_backend_asm_features_nocache
@features.appsec_onboarding
class Test_RemoteConfigurationUpdateSequenceFeaturesNoCache(RemoteConfigurationFieldsBasicTests):
    """
        Tests that over a sequence of related updates, tracers follow the RFC for the Features product
        This test is not relevant for all tracers but C++ and ruby (missing feature). It may be never used
        if those languages directly implements  cache feature.

        It may be brokken as it's using the new RC API, and thus may have a additional
        RC request between each payload. But we do not have a way to check that.
    """

    request_number = 0

    def setup_tracer_update_sequence(self):
        with open("tests/remote_config/rc_mocked_responses_asm_features_nocache.json", "r", encoding="utf-8") as f:
            payloads = json.load(f)

        for payload in payloads:
            remote_config.send_command(payload, wait_for_acknowledged_status=False)

    def test_tracer_update_sequence(self):
        """test update sequence, based on a scenario mocked in the proxy"""

        self.assert_client_fields()

        def validate(data):
            """Helper to validate config request content"""
            logger.info(f"validating request number {self.request_number}")
            if self.request_number >= len(ASM_FEATURES_EXPECTED_REQUESTS):
                return True

            rc_check_request(data, ASM_FEATURES_EXPECTED_REQUESTS[self.request_number], caching=False)

            self.request_number += 1

            return False

        interfaces.library.validate_remote_configuration(validator=validate)


@rfc("https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph")
@scenarios.remote_config_mocked_backend_live_debugging_nocache
@features.remote_config_object_supported
class Test_RemoteConfigurationUpdateSequenceLiveDebuggingNoCache(RemoteConfigurationFieldsBasicTests):
    """
        Tests that over a sequence of related updates, tracers follow the RFC for the Live Debugging product
    
        It may be brokken as it's using the new RC API, and thus may have a additional
        RC request between each payload. But we do not have a way to check that.
    """

    request_number = defaultdict(int)

    def setup_tracer_update_sequence(self):
        with open("tests/remote_config/rc_mocked_responses_live_debugging_nocache.json", "r", encoding="utf-8") as f:
            payloads = json.load(f)

        for payload in payloads:
            remote_config.send_command(payload, wait_for_acknowledged_status=False)

    def test_tracer_update_sequence(self):
        """test update sequence, based on a scenario mocked in the proxy"""

        self.assert_client_fields()

        def validate(data):
            """Helper to validate config request content"""
            runtime_id = data["request"]["content"]["client"]["client_tracer"]["runtime_id"]
            logger.info(f"validating request number {self.request_number[runtime_id]}")
            if self.request_number[runtime_id] >= len(LIVE_DEBUGGING_EXPECTED_REQUESTS):
                return True

            rc_check_request(data, LIVE_DEBUGGING_EXPECTED_REQUESTS[self.request_number[runtime_id]], caching=False)

            self.request_number[runtime_id] += 1

            return False

        interfaces.library.validate_remote_configuration(validator=validate)


@rfc("https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph")
@scenarios.remote_config_mocked_backend_asm_dd_nocache
@features.remote_config_object_supported
class Test_RemoteConfigurationUpdateSequenceASMDDNoCache(RemoteConfigurationFieldsBasicTests):
    """Tests that over a sequence of related updates, tracers follow the RFC for the ASM DD product
    
        It may be brokken as it's using the new RC API, and thus may have a additional
        RC request between each payload. But we do not have a way to check that.
    """

    request_number = 0

    def setup_tracer_update_sequence(self):
        with open("tests/remote_config/rc_mocked_responses_asm_dd_nocache.json", "r", encoding="utf-8") as f:
            payloads = json.load(f)

        for payload in payloads:
            remote_config.send_command(payload, wait_for_acknowledged_status=False)

    def test_tracer_update_sequence(self):
        """test update sequence, based on a scenario mocked in the proxy"""

        self.assert_client_fields()

        def validate(data):
            """Helper to validate config request content"""
            logger.info(f"validating request number {self.request_number}")
            if self.request_number >= len(ASM_DD_EXPECTED_REQUESTS):
                return True

            rc_check_request(data, ASM_DD_EXPECTED_REQUESTS[self.request_number], caching=False)

            self.request_number += 1

            return False

        interfaces.library.validate_remote_configuration(validator=validate)
