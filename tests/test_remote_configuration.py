# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


from utils import context, BaseTestCase, interfaces, bug, irrelevant, missing_feature, flaky, released, rfc, coverage
import json


@rfc("add here")
@coverage.basic
class Test_RemoteConfiguration(BaseTestCase):
    """Remote configuration"""

    def test_language(self):
        def validator(data):
            assert "client" in data["request"]["content"], f"'client' is missing in {data['log_filename']}"
            assert (
                "client_tracer" in data["request"]["content"]["client"]
            ), f"'client_tracer' is missing in {data['log_filename']}"

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


@coverage.basic
class Test_RemoteConfigurationUpdateSequence(BaseTestCase):
    """Remote configuration update sequence"""

    current_test = -1
    number_of_tests = 13

    def test_tracer_update_sequence(self):
        def load_expected_payload(test_no):
            path = "???/r{}.json".format(test_no)
            f = open(path, "r")
            payload = json.load(f)
            f.close()
            return payload

        def validator(data):
            # We have a finite set of tests, if we've made it past that without an assertion
            # failure, we're done!
            if self.current_test == self.number_of_tests:
                return True

            target_version = data["request"]["content"]["client"]["state"]["targetsVersion"]
            config_states = data["request"]["content"]["client"]["state"]["configStates"]
            cached_target_files = data["request"]["content"]["cachedTargetFiles"]

            # Note: we could encode the first expected request from the tracer in JSON too
            # to simplify this. Otherwise each request works the same way - load the expected
            # payload and compare the important fields.
            if self.current_test == -1:
                assert target_version != 0
                assert not config_states
                assert not cached_target_files
            else:
                expected = load_expected_payload(self.current_test)

                assert target_version == expected["client"]["state"]["targetsVersion"]

                expected_config_states = expected["client"]["state"]["configStates"]
                assert len(expected_config_states) == len(config_states)
                for state in config_states:
                    assert state in expected_config_states

                expected_cached_target_files = expected["cachedTargetFiles"]
                assert len(expected_cached_target_files) == len(cached_target_files)
                for file in cached_target_files:
                    assert file in expected_cached_target_files

            self.current_test += 1

            return None

        interfaces.library.add_remote_configuration_validation(validator=validator, is_success_on_expiry=True)
