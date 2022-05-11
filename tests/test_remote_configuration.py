# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


from utils import context, BaseTestCase, interfaces, bug, irrelevant, missing_feature, flaky, released, rfc, coverage


@rfc("add here")
@coverage.basic
class Test_RemoteConfiguration(BaseTestCase):
    """ Remote configuration """

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
