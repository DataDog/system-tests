# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import rfc, coverage, interfaces, features


@rfc("https://docs.google.com/document/d/1bUVtEpXNTkIGvLxzkNYCxQzP2X9EK9HMBLHWXr_5KLM/edit#heading=h.vy1jegxy7cuc")
@coverage.basic
@features.remote_config_object_supported
class Test_NoError:
    """A library should apply with no error all remote config payload."""

    def test_no_error(self):
        def no_error(data):
            config_states = (
                data.get("request", {}).get("content", {}).get("client", {}).get("state", {}).get("config_states", {})
            )

            for state in config_states:
                error = state.get("apply_error", None)
                if error is not None:
                    raise Exception(f"Error in remote config application: {error}")

        interfaces.library.validate_remote_configuration(no_error, success_by_default=True)
