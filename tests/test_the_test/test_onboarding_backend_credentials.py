import requests

from utils import pytest
from utils.onboarding import backend_interface


pytestmark = pytest.mark.scenario("TEST_THE_TEST")


@pytest.mark.parametrize("query", ["trace", "profile"])
def test_backend_failure_locals_hide_authentication_keys(monkeypatch: pytest.MonkeyPatch, query: str) -> None:
    # Only backend frames belong in the failure rendering under test.
    __tracebackhide__ = True
    monkeypatch.setenv("DD_API_KEY_ONBOARDING", "synthetic-onboarding-api-key")
    monkeypatch.setenv("DD_APP_KEY_ONBOARDING", "synthetic-onboarding-app-key")
    monkeypatch.delenv("DD_API_KEY_ONBOARDING_2", raising=False)
    monkeypatch.delenv("DD_APP_KEY_ONBOARDING_2", raising=False)
    prepared_requests: list[requests.PreparedRequest] = []

    def unavailable_response(
        _session: requests.Session, request: requests.PreparedRequest, **_kwargs: object
    ) -> requests.Response:
        prepared_requests.append(request)
        response = requests.Response()
        response.status_code = 503
        return response

    monkeypatch.setattr(requests.Session, "send", unavailable_response)
    times = iter([0, 400])
    monkeypatch.setattr(backend_interface.time, "perf_counter", lambda: next(times))

    with pytest.raises(TimeoutError) as failure:
        if query == "trace":
            backend_interface._query_for_trace_id("synthetic-trace-id")  # noqa: SLF001
        else:
            backend_interface._query_for_profile("synthetic-runtime-id")  # noqa: SLF001

    request = prepared_requests[0]
    assert request.headers["DD-API-KEY"] == "synthetic-onboarding-api-key"
    assert request.headers["DD-APPLICATION-KEY"] == "synthetic-onboarding-app-key"
    if query == "profile":
        assert request.headers["Content-Type"] == "application/json"

    failure_output = str(failure.getrepr(showlocals=True))
    assert "synthetic-onboarding-api-key" not in failure_output
    assert "synthetic-onboarding-app-key" not in failure_output
    assert "<redacted>" in failure_output
    assert "Reached overall timeout" in failure_output
    assert request.url is not None
    assert request.url in failure_output
