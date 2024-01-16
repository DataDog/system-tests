import pytest

from utils import (
    coverage,
    features,
    interfaces,
    rfc,
    scenarios,
    weblog,
)


def get_schema(request, address):
    """get api security schema from spans"""
    for _, _, span in interfaces.library.get_spans(request):
        meta = span.get("meta", {})
        payload = meta.get("_dd.appsec.s." + address)
        if payload is not None:
            return payload
    return


@rfc(
    "https://docs.google.com/document/d/1OCHPBCAErOL2FhLl64YAHB8woDyq66y5t-JGolxdf1Q/edit#heading=h.bth088vsbjrz"
)
@coverage.basic
@scenarios.appsec_api_security
@features.api_security_schemas
@pytest.mark.parametrize(
    "library_env",
    [
        {"DD_API_SECURITY_REQUEST_SAMPLE_RATE": "0.0"},
        {"DD_API_SECURITY_REQUEST_SAMPLE_RATE": "0.1"},
        {"DD_API_SECURITY_REQUEST_SAMPLE_RATE": "0.5"},
        {"DD_API_SECURITY_REQUEST_SAMPLE_RATE": "0.9"},
        {"DD_API_SECURITY_REQUEST_SAMPLE_RATE": "1.0"},
    ],
)
class Test_API_Security_sampling:
    """Test API Security - Request Headers Schema"""

    N = 20  # square root of number of requests

    @pytest.fixture(scope="function")
    def setup_and_teardown(self, library_env):
        print(">>> setup_request_method", library_env)
        self.all_requests = [
            weblog.get("/tag_value/api_match_AS001/200") for _ in range(self.N**2)
        ]
        yield

    def test_sampling_rate(self, library_env, setup_and_teardown):
        """can provide request header schema"""
        N = self.N
        assert all(r.status_code == 200 for r in self.all_requests)
        s = sum(get_schema(r, "req.headers") is not None for r in self.all_requests)
        # check result is in at most 4 standard deviations from expected
        # (assuming 99.98% confidence interval)
        match library_env["DD_API_SECURITY_REQUEST_SAMPLE_RATE"]:
            case "0.0":
                assert s == 0
            case "0.1":
                assert (N**2) * 0.1 - 1.2 * N <= s <= (N**2) * 0.1 + 1.2 * N
            case "0.5":
                assert (N**2) * 0.5 - 2 * N <= s <= (N**2) * 0.5 + 2 * N
            case "0.9":
                assert (N**2) * 0.9 - 1.2 * N <= s <= (N**2) * 0.9 + 1.2 * N
            case "1.0":
                assert s == N**2
