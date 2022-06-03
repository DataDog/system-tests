# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


from utils import BaseTestCase, interfaces, released, rfc, coverage, proxies, context
import json


@rfc("add RFC link here")  # TODO
@released(cpp="?", dotnet="?", java="?", php="?", python="?", ruby="?")
@coverage.basic
class Test_RemoteConfiguration(BaseTestCase):
    """Remote configuration"""

    def setUp(self):
        proxies.library.set_state("mock_remote_config_backend", True)

    def test_language(self):
        def validator(data):
            content = data["request"]["content"]
            assert "client" in content, f"'client' is missing in {data['log_filename']}"
            assert "client_tracer" in content["client"], f"'client_tracer' is missing in {data['log_filename']}"

            language = data["request"]["content"]["client"]["client_tracer"].get("language")

            expected_language = {
                "cpp": "cpp",
                "dotnet": "dotnet",
                "golang": "go",
                "nodejs": "nodejs",
                "java": "java",
                "php": "php",
                "python": "python",
                "ruby": "ruby",
            }[context.library.library]

            assert language == expected_language, f"language is '{language}', I was expecting '{expected_language}'"

        interfaces.library.add_remote_configuration_validation(validator=validator, is_success_on_expiry=True)


@rfc("add RFC link here")  # TODO
@released(cpp="?", dotnet="?", java="?", php="?", python="?", ruby="?")
@coverage.basic
class Test_RemoteConfigurationUpdateSequence(BaseTestCase):
    """Remote configuration update sequence"""

    request_number = 0

    def test_tracer_update_sequence(self):
        """ test update sequence, based on a scenario mocked in the proxy """

        def validate_content(data, expected_targets_version, expected_config_states, expected_cached_target_files):
            """ Helper to validate config request content """

            content = data["request"]["content"]
            client_state = content["client"]["state"]

            targets_version = client_state["targetsVersion"]
            if targets_version != expected_targets_version:
                raise Exception("targetsVersion was expected to be {expected_targets_version}, not {targets_version}")

            config_states = client_state["configStates"]
            assert len(config_states) == len(expected_config_states)
            for state in expected_config_states:
                assert state in config_states, f"{state} is not in {config_states}"

            cached_target_files = content["cachedTargetFiles"]
            assert len(cached_target_files) == len(expected_cached_target_files)
            for file in expected_cached_target_files:
                assert file in cached_target_files, f"{file} is not in {cached_target_files}"

        def validate_contents(data):
            self.request_number += 1

            if self.request_number == 1:
                # Checks on initial request made by the library

                content = data["request"]["content"]
                client_state = content["client"]["state"]

                # TODO, state is actually an empty object, so it fails.
                assert client_state.get("targetsVersion", 0) != 0, "targetsVersion should not be 0"
                assert "configStates" not in client_state, "configStates must not be in config initial request"
                assert "cachedTargetFiles" not in content, "cachedTargetFiles must not be in config initial request"

            elif self.request_number == 2:
                # The response of request #1 has been mocked by <explain response content>
                # so we expect the library to do this request now :

                validate_content(
                    data,
                    expected_targets_version=["xxx", "yyyy",],
                    expected_config_states=["xxx", "yyyy",],
                    expected_cached_target_files=["xxx", "yyyy",],
                )

            elif self.request_number == 3:
                # The response of request #2 has been mocked by <explain response content>
                # so we expect the library to do this request now :

                validate_content(
                    data,
                    expected_targets_version=["yyy", "zzz",],
                    expected_config_states=["yyy", "zzz",],
                    expected_cached_target_files=["yyy", "zzz",],
                )

                # It was the last request we expected for, so return True tells that the test is ok
                return True

        interfaces.library.add_remote_configuration_validation(validator=validate_contents)
