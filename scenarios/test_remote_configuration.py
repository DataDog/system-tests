# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, interfaces, released, rfc, coverage, proxies, context
import json


@rfc("https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph")
@released(cpp="?", dotnet="?", java="?", php="?", python="?", ruby="?", nodejs="?")
@coverage.basic
class Test_RemoteConfigurationTracerLanguage(BaseTestCase):
    """ Ensure that tracer clients use the correct word for the language """

    def test_tracer_language(self):
        def validator(data):
            content = data["request"]["content"]
            assert "client" in content, f"'client' is missing in {data['log_filename']}"
            assert "client_tracer" in content["client"], f"'client_tracer' is missing in {data['log_filename']}"

            language = data["request"]["content"]["client"]["client_tracer"].get("language")

            expected_language = {
                "cpp": "cpp",
                "dotnet": "dot_net",
                "golang": "go",
                "nodejs": "node",
                "java": "java",
                "php": "php",
                "python": "python",
                "ruby": "ruby",
            }[context.library.library]

            assert language == expected_language, f"language is '{language}', I was expecting '{expected_language}'"

        interfaces.library.add_remote_configuration_validation(validator=validator, is_success_on_expiry=True)


@rfc("https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph")
@released(cpp="?", dotnet="?", java="?", php="?", python="?", ruby="?", nodejs="?")
@coverage.basic
class Test_RemoteConfigurationClientStateRequestData(BaseTestCase):
    """ Ensure that the Client State field is filled out apppropriately in update requests """

    def test_client_state_fields(self):
        def validator(data):
            content = data["request"]["content"]

            assert "client" in content, f"'client' is missing in {data['log_filename']}"
            assert "state" in content["client"], f"'state' is a required field for tracer update requests"

            state = content["client"]["state"]
            assert (
                "root_version" in state
            ), f"'client.state.root_version' is a required field for tracer update requests"
            assert (
                "targets_version" in state
            ), f"'client.state.targets_version' is a required field for tracer update requests"

            assert (
                state["root_version"] == 1
            ), f"'client.state.root_version' must be set to 1 until root updates are supported"

            if "has_error" in state:
                assert (
                    "error" in state and state["error"] != ""
                ), f"'client.state.error' must be non-empty if a client reports an error with 'client.state.has_error'"

        interfaces.library.add_remote_configuration_validation(validator=validator, is_success_on_expiry=True)


@rfc("https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph")
@released(cpp="?", dotnet="?", java="?", php="?", python="?", ruby="?", nodejs="?")
@coverage.basic
class Test_RemoteConfigurationClientRequestData(BaseTestCase):
    """ Ensure that the Client field is appropriately filled out in update requests"""

    def test_client_fields(self):
        def validator(data):
            content = data["request"]["content"]

            assert "client" in content, f"'client' is missing in {data['log_filename']}"
            client = content["client"]
            assert (
                "is_tracer" in client and client["is_tracer"] == True
            ), f"'client.is_tracer' MUST be set to true for tracer clients"
            assert (
                "products" in client and len(client["products"]) > 0
            ), f"'client.products' MUST be set and be non-empty"
            assert "id" in client and client["id"] != "", f"'client.id' MUST be set and be non-empty"
            assert (
                "is_agent" not in client 
            ), f"'client.is_agent' MUST either NOT be set or set to false"
            assert "client_agent" not in client, f"'client.client_agent' must NOT be set"

            assert "client_tracer" in client, f"'client.client_tracer' MUST be present for tracer clients"
            client_tracer = content["client"]["client_tracer"]
            assert (
                "runtime_id" in client_tracer and client_tracer["runtime_id"] != ""
            ), f"'client.client_tracer.runtime_id' must be present and non-empty"
            assert (
                client["id"] != client_tracer["runtime_id"]
            ), f"'client.id' and 'client.client_tracer.runtime_id' must be distinct"
            assert (
                "service" in client_tracer and client_tracer["service"] != ""
            ), f"'client.client_tracer.service' must be present and non-empty"
            assert (
                "env" in client_tracer and client_tracer["env"] != ""
            ), f"'client.client_tracer.env' must be present and non-empty"
            assert (
                "app_version" in client_tracer and client_tracer["app_version"] != ""
            ), f"'client.client_tracer.app_version' must be present and non-empty"
            assert (
                "tracer_version" in client_tracer and client_tracer["tracer_version"] != ""
            ), f"'client.client_tracer.tracer_version' must be present and non-empty"

        interfaces.library.add_remote_configuration_validation(validator=validator, is_success_on_expiry=True)


@rfc("https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph")
@released(cpp="?", dotnet="?", java="?", php="?", python="?", ruby="?", nodejs="?")
@coverage.basic
class Test_RemoteConfigurationUpdateSequence(BaseTestCase):
    """Tests that over a sequence of related updates, tracers follow the RFC"""

    request_number = -1

    # Tracers have to send us their state with every update request. Since we are mocking the agent's responses in these tests, we know exactly what
    # they should be sending us as their state, allowing us to test their RFC compliance.
    EXPECTED_REQUESTS = [
        b'{"client":{"state":{"targets_version":1}}}',
        b'{"client":{"state":{"targets_version":2,"config_states":[{"id":"asmdd1","version":1,"product":"ASM_DD"}]}},"cached_target_files":[{"path":"datadog/2/ASM_DD/asmdd1/config","length":3,"hashes":[{"algorithm":"sha256","hash":"LCa0a2j/xo/5m0U8HTBBNBNCLXBkg7+g+YpeiGJm564="}]}]}',
        b'{"client":{"state":{"targets_version":3,"config_states":[{"id":"asmdd1","version":1,"product":"ASM_DD"},{"id":"features1","version":1,"product":"FEATURES"}]}},"cached_target_files":[{"path":"datadog/2/ASM_DD/asmdd1/config","length":3,"hashes":[{"algorithm":"sha256","hash":"LCa0a2j/xo/5m0U8HTBBNBNCLXBkg7+g+YpeiGJm564="}]},{"path":"datadog/2/FEATURES/features1/config","length":25,"hashes":[{"algorithm":"sha256","hash":"6ZykRo3MgylZ6FwvGYS1bNx4tSEX1sVpjCTTWaoGnDo="}]}]}',
        b'{"client":{"state":{"targets_version":4,"config_states":[{"id":"asmdd1","version":2,"product":"ASM_DD"},{"id":"features1","version":1,"product":"FEATURES"}]}},"cached_target_files":[{"path":"datadog/2/ASM_DD/asmdd1/config","length":3,"hashes":[{"algorithm":"sha256","hash":"/N4rLtula/QIYB+3If6bXDONEO5CnqBPrlURto+/j7k="}]},{"path":"datadog/2/FEATURES/features1/config","length":25,"hashes":[{"algorithm":"sha256","hash":"6ZykRo3MgylZ6FwvGYS1bNx4tSEX1sVpjCTTWaoGnDo="}]}]}',
        b'{"client":{"state":{"targets_version":5,"config_states":[{"id":"features1","version":1,"product":"FEATURES"},{"id":"features2","version":1,"product":"FEATURES"}]}},"cached_target_files":[{"path":"datadog/2/FEATURES/features1/config","length":25,"hashes":[{"algorithm":"sha256","hash":"6ZykRo3MgylZ6FwvGYS1bNx4tSEX1sVpjCTTWaoGnDo="}]},{"path":"datadog/2/FEATURES/features2/config","length":24,"hashes":[{"algorithm":"sha256","hash":"AVllirhb5yB3YaQREXKwFVg5S/x0of4dMU8gI/fGVts="}]}]}',
        b'{"client":{"state":{"targets_version":6,"config_states":[{"id":"features1","version":2,"product":"FEATURES"},{"id":"asmdd1","version":3,"product":"ASM_DD"}]}},"cached_target_files":[{"path":"datadog/2/FEATURES/features1/config","length":24,"hashes":[{"algorithm":"sha256","hash":"AVllirhb5yB3YaQREXKwFVg5S/x0of4dMU8gI/fGVts="}]},{"path":"datadog/2/ASM_DD/asmdd1/config","length":3,"hashes":[{"algorithm":"sha256","hash":"/N4rLtula/QIYB+3If6bXDONEO5CnqBPrlURto+/j7k="}]}]}',
        b'{"client":{"state":{"targets_version":7,"config_states":[{"id":"features3","version":1,"product":"FEATURES"},{"id":"asmdd1","version":3,"product":"ASM_DD"},{"id":"features1","version":2,"product":"FEATURES"}]}},"cached_target_files":[{"path":"datadog/2/FEATURES/features3/config","length":46,"hashes":[{"algorithm":"sha256","hash":"E6dpL2JfUiVkjMa2I4yfu9IgvLsVk3p0kBHN9lIF4hM="}]},{"path":"datadog/2/ASM_DD/asmdd1/config","length":3,"hashes":[{"algorithm":"sha256","hash":"/N4rLtula/QIYB+3If6bXDONEO5CnqBPrlURto+/j7k="}]},{"path":"datadog/2/FEATURES/features1/config","length":24,"hashes":[{"algorithm":"sha256","hash":"AVllirhb5yB3YaQREXKwFVg5S/x0of4dMU8gI/fGVts="}]}]}',
        b'{"client":{"state":{"targets_version":7,"config_states":[{"id":"features3","version":1,"product":"FEATURES"},{"id":"asmdd1","version":3,"product":"ASM_DD"},{"id":"features1","version":2,"product":"FEATURES"}]}},"cached_target_files":[{"path":"datadog/2/FEATURES/features3/config","length":46,"hashes":[{"algorithm":"sha256","hash":"E6dpL2JfUiVkjMa2I4yfu9IgvLsVk3p0kBHN9lIF4hM="}]},{"path":"datadog/2/ASM_DD/asmdd1/config","length":3,"hashes":[{"algorithm":"sha256","hash":"/N4rLtula/QIYB+3If6bXDONEO5CnqBPrlURto+/j7k="}]},{"path":"datadog/2/FEATURES/features1/config","length":24,"hashes":[{"algorithm":"sha256","hash":"AVllirhb5yB3YaQREXKwFVg5S/x0of4dMU8gI/fGVts="}]}]}',
        b'{"client":{"state":{"targets_version":8,"config_states":[{"id":"asmdd1","version":3,"product":"ASM_DD"},{"id":"features1","version":2,"product":"FEATURES"},{"id":"features3","version":1,"product":"FEATURES"}]}},"cached_target_files":[{"path":"datadog/2/ASM_DD/asmdd1/config","length":3,"hashes":[{"algorithm":"sha256","hash":"/N4rLtula/QIYB+3If6bXDONEO5CnqBPrlURto+/j7k="}]},{"path":"datadog/2/FEATURES/features1/config","length":24,"hashes":[{"algorithm":"sha256","hash":"AVllirhb5yB3YaQREXKwFVg5S/x0of4dMU8gI/fGVts="}]},{"path":"datadog/2/FEATURES/features3/config","length":46,"hashes":[{"algorithm":"sha256","hash":"E6dpL2JfUiVkjMa2I4yfu9IgvLsVk3p0kBHN9lIF4hM="}]}]}',
        b'{"client":{"state":{"targets_version":9,"config_states":[{"id":"features1","version":2,"product":"FEATURES"},{"id":"features3","version":1,"product":"FEATURES"},{"id":"asmdd4","version":1,"product":"ASM_DD"},{"id":"asmdd1","version":3,"product":"ASM_DD"}]}},"cached_target_files":[{"path":"datadog/2/FEATURES/features1/config","length":24,"hashes":[{"algorithm":"sha256","hash":"AVllirhb5yB3YaQREXKwFVg5S/x0of4dMU8gI/fGVts="}]},{"path":"datadog/2/FEATURES/features3/config","length":46,"hashes":[{"algorithm":"sha256","hash":"E6dpL2JfUiVkjMa2I4yfu9IgvLsVk3p0kBHN9lIF4hM="}]},{"path":"datadog/2/ASM_DD/asmdd4/config","length":5,"hashes":[{"algorithm":"sha256","hash":"SG6kYiTRu0+2gPNPfJrZao8k7Ii+c+qOWmxlJg6cuKc="}]},{"path":"datadog/2/ASM_DD/asmdd1/config","length":3,"hashes":[{"algorithm":"sha256","hash":"/N4rLtula/QIYB+3If6bXDONEO5CnqBPrlURto+/j7k="}]}]}',
        b'{"client":{"state":{"targets_version":10,"config_states":[{"id":"asmdd4","version":1,"product":"ASM_DD"},{"id":"asmdd1","version":3,"product":"ASM_DD"},{"id":"features1","version":2,"product":"FEATURES"},{"id":"features3","version":1,"product":"FEATURES"}]}},"cached_target_files":[{"path":"datadog/2/ASM_DD/asmdd4/config","length":5,"hashes":[{"algorithm":"sha256","hash":"SG6kYiTRu0+2gPNPfJrZao8k7Ii+c+qOWmxlJg6cuKc="}]},{"path":"datadog/2/ASM_DD/asmdd1/config","length":3,"hashes":[{"algorithm":"sha256","hash":"/N4rLtula/QIYB+3If6bXDONEO5CnqBPrlURto+/j7k="}]},{"path":"datadog/2/FEATURES/features1/config","length":24,"hashes":[{"algorithm":"sha256","hash":"AVllirhb5yB3YaQREXKwFVg5S/x0of4dMU8gI/fGVts="}]},{"path":"datadog/2/FEATURES/features3/config","length":46,"hashes":[{"algorithm":"sha256","hash":"E6dpL2JfUiVkjMa2I4yfu9IgvLsVk3p0kBHN9lIF4hM="}]}]}',
        b'{"client":{"state":{"targets_version":11,"config_states":[{"id":"asmdd1","version":3,"product":"ASM_DD"},{"id":"features1","version":2,"product":"FEATURES"},{"id":"features3","version":1,"product":"FEATURES"},{"id":"asmdd4","version":1,"product":"ASM_DD"}]}},"cached_target_files":[{"path":"datadog/2/ASM_DD/asmdd1/config","length":3,"hashes":[{"algorithm":"sha256","hash":"/N4rLtula/QIYB+3If6bXDONEO5CnqBPrlURto+/j7k="}]},{"path":"datadog/2/FEATURES/features1/config","length":24,"hashes":[{"algorithm":"sha256","hash":"AVllirhb5yB3YaQREXKwFVg5S/x0of4dMU8gI/fGVts="}]},{"path":"datadog/2/FEATURES/features3/config","length":46,"hashes":[{"algorithm":"sha256","hash":"E6dpL2JfUiVkjMa2I4yfu9IgvLsVk3p0kBHN9lIF4hM="}]},{"path":"datadog/2/ASM_DD/asmdd4/config","length":5,"hashes":[{"algorithm":"sha256","hash":"SG6kYiTRu0+2gPNPfJrZao8k7Ii+c+qOWmxlJg6cuKc="}]}]}',
    ]

    def test_tracer_update_sequence(self):
        """ test update sequence, based on a scenario mocked in the proxy """

        def validate_content(data, request_number):
            """ Helper to validate config request content """

            expected = json.loads(self.EXPECTED_REQUESTS[request_number])

            content = data["request"]["content"]
            client_state = content["client"]["state"]

            # client.state must always be present in the request. The data can be empty, but the object must always be present.
            assert client_state, "client.state must always be included in tracer client requests"

            # verify that the tracer properly updated the TUF targets version, if it's not included we assume it to be 0 in the agent.
            # Our test suite will always emit SOMETHING for this
            expected_targets_version = expected["client"]["state"]["targets_version"]
            targets_version = client_state.get("targets_version", 0)
            assert (
                targets_version == expected_targets_version
            ), f"targetsVersion was expected to be {expected_targets_version}, not {targets_version}"

            # verify that the tracer is properly storing and reporting on its config state
            expected_config_states = expected["client"]["state"].get("config_states")
            config_states = client_state.get("config_states")
            if expected_config_states is None and config_states is not None:
                raise Exception("client is not expected to have stored config but is reporting stored configs")
            elif expected_config_states is not None and config_states is None:
                raise Exception("client is expected to have stored confis but isn't reporting any")
            elif config_states is not None:
                assert len(config_states) == len(
                    expected_config_states
                ), "client reporting more or less configs than expected"
                for state in expected_config_states:
                    assert state in config_states, f"{state} is not in {config_states}"

            # verify that the tracer is properly storing and reporting on its local cached files
            # The RFC allows for the tracer clients to cache, or not at all. If they decide to cache, they must
            # properly retain all active configs and discard evicted configs, allowing us to test. By including
            # the cached_target_files field they are opting in to caching in the eyes of our test.
            expected_cached_target_files = expected.get("cached_target_files")
            cached_target_files = content.get("cached_target_files")
            if expected_cached_target_files is None and cached_target_files is not None:
                raise Exception("client is not expected to have cached config but is reporting cached config")
            elif cached_target_files is not None:
                assert len(cached_target_files) == len(expected_cached_target_files)
                for file in expected_cached_target_files:
                    assert file in cached_target_files, f"{file} is not in {cached_target_files}"

        def validate_contents(data):
            content = data["request"]["content"]

            if self.request_number == len(self.EXPECTED_REQUESTS):
                return True

            if self.request_number != -1:
                validate_content(data, self.request_number)

            self.request_number += 1

        interfaces.library.add_remote_configuration_validation(validator=validate_contents)
