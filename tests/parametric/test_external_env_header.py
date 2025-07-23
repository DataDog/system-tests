import pytest
from utils import scenarios, features, missing_feature, context


@features.datadog_headers_propagation
@scenarios.parametric
class Test_External_Env_Header:
    @missing_feature(library="php", reason="not implemented yet")
    @missing_feature(library="ruby", reason="not implemented yet")
    @missing_feature(context.library < "golang@1.73.0-dev", reason="Implemented in v1.72.0")
    @pytest.mark.parametrize(
        "library_env",
        [
            {"DD_EXTERNAL_ENV": "test-env-value"},
            {"DD_EXTERNAL_ENV": "prod-env,staging-env"},
            {"DD_EXTERNAL_ENV": "it-false,cn-weblog,pu-75a2b6d5-3949-4afb-ad0d-92ff0674e759"},
        ],
    )
    def test_datadog_external_env_header_set(self, test_agent, test_library, library_env):
        """Ensure that the datadog-external-env header is correctly set in requests to the test agent
        with the value from the DD_EXTERNAL_ENV environment variable.
        """
        with test_library:
            # Create a span to generate a trace that will be sent to the agent
            test_library.dd_start_span("test_span")

        # Wait for the trace to be sent to the agent
        test_agent.wait_for_num_traces(1)

        # Get all requests made to the agent
        requests = test_agent.requests()

        # Find requests to the traces endpoint
        trace_requests = [req for req in requests if req["url"].endswith("/traces")]

        # Verify that at least one trace request was made
        assert len(trace_requests) > 0, "No trace requests found"

        # Check that the datadog-external-env header is present and has the correct value
        for request in trace_requests:
            headers = request["headers"]
            assert (
                "datadog-external-env" in headers
            ), f"datadog-external-env header missing in request to {request['url']}"

            # Get the expected value from the library_env parameter
            expected_value = library_env.get("DD_EXTERNAL_ENV")
            assert expected_value is not None, "DD_EXTERNAL_ENV environment variable not set"

            # Verify the header value matches the environment variable
            actual_value = headers["datadog-external-env"]
            assert actual_value == expected_value, (
                f"datadog-external-env header value '{actual_value}' does not match "
                f"DD_EXTERNAL_ENV environment variable '{expected_value}'"
            )

    @missing_feature(library="php", reason="not implemented yet")
    @missing_feature(library="ruby", reason="not implemented yet")
    @missing_feature(context.library < "golang@1.73.0-dev", reason="Implemented in v1.72.0")
    def test_datadog_external_env_header_not_set_when_env_var_missing(self, test_agent, test_library, library_env):
        """Ensure that the datadog-external-env header is not set when DD_EXTERNAL_ENV environment variable is not present."""
        with test_library:
            # Create a span to generate a trace that will be sent to the agent
            test_library.dd_start_span("test_span")

        # Wait for the trace to be sent to the agent
        test_agent.wait_for_num_traces(1)

        # Get all requests made to the agent
        requests = test_agent.requests()

        # Find requests to the traces endpoint
        trace_requests = [req for req in requests if req["url"].endswith("/traces")]

        # Verify that at least one trace request was made
        assert len(trace_requests) > 0, "No trace requests found"

        # Check that the datadog-external-env header is not present when DD_EXTERNAL_ENV is not set
        for request in trace_requests:
            headers = request["headers"]
            # The header should not be present when DD_EXTERNAL_ENV is not set
            assert "datadog-external-env" not in headers, (
                f"datadog-external-env header should not be present when DD_EXTERNAL_ENV is not set, "
                f"but found value: {headers.get('datadog-external-env')}"
            )
