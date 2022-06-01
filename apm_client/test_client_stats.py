import pytest


parametrize = pytest.mark.parametrize
snapshot = pytest.mark.snapshot


@snapshot
@parametrize(
    "apm_test_server_env",
    [
        {
            "DD_TRACE_COMPUTE_STATS": "1",
        }
    ],
)
def test_client_trace(test_agent, test_client, apm_test_server_env):
    with test_client.start_span(name="web.request", service="webserver") as span:
        with test_client.start_span(name="postgres.query", service="postgres", parent_id=span.span_id):
            pass
    test_client.flush()

    stats = test_agent.requests()
