from datetime import UTC, datetime
import json

import requests

from utils import pytest
from utils.onboarding import backend_interface


pytestmark = pytest.mark.scenario("TEST_THE_TEST")


@pytest.mark.parametrize("profile", [False, True])
def test_backend_failure_reports_omit_authentication_headers(monkeypatch: pytest.MonkeyPatch, *, profile: bool) -> None:
    # Only backend frames belong in the failure rendering under test.
    __tracebackhide__ = True
    monkeypatch.setenv("DD_API_KEY_ONBOARDING", "synthetic-onboarding-api-key")
    monkeypatch.setenv("DD_APP_KEY_ONBOARDING", "synthetic-onboarding-app-key")
    monkeypatch.delenv("DD_API_KEY_ONBOARDING_2", raising=False)
    monkeypatch.delenv("DD_APP_KEY_ONBOARDING_2", raising=False)
    prepared_requests: list[requests.PreparedRequest] = []

    def backend_response(
        _session: requests.Session, request: requests.PreparedRequest, **_kwargs: object
    ) -> requests.Response:
        prepared_requests.append(request)
        response = requests.Response()
        response.status_code = 503
        if profile and len(prepared_requests) == 1:
            response.status_code = 200
            response._content = json.dumps(  # noqa: SLF001
                {
                    "trace": {
                        "root_id": "root",
                        "spans": {
                            "root": {
                                "start": datetime.now(tz=UTC).timestamp(),
                                "meta": {"runtime-id": "synthetic-runtime-id"},
                            }
                        },
                    }
                }
            ).encode()
        return response

    monkeypatch.setattr(requests.Session, "send", backend_response)
    times = iter([0, 0, 400] if profile else [0, 400])
    monkeypatch.setattr(backend_interface.time, "perf_counter", lambda: next(times))

    with pytest.raises(TimeoutError) as failure:
        backend_interface.wait_backend_trace_id("synthetic-trace-id", profile=profile)

    request = prepared_requests[-1]
    assert request.headers["DD-API-KEY"] == "synthetic-onboarding-api-key"
    assert request.headers["DD-APPLICATION-KEY"] == "synthetic-onboarding-app-key"
    if profile:
        assert request.headers["Content-Type"] == "application/json"

    failure_output = str(failure.getrepr(showlocals=True))
    assert "synthetic-onboarding-api-key" not in failure_output
    assert "synthetic-onboarding-app-key" not in failure_output
    assert "DD-API-KEY" not in failure_output
    assert "DD-APPLICATION-KEY" not in failure_output
    assert "wait_backend_trace_id" in failure_output
    assert "synthetic-trace-id" in failure_output
    assert "Reached overall timeout" in failure_output
    assert ("post" if profile else "get") in failure_output
    assert request.url is not None
    assert request.url in failure_output
