from utils import (
    bug,
    context,
    features,
    interfaces,
    irrelevant,
    rfc,
    scenarios,
    weblog,
)

from utils.tools import logger
import random
import string
import time


def get_schema(request, address):
    """get api security schema from spans"""
    for _, _, span in interfaces.library.get_spans(request):
        meta = span.get("meta", {})
        payload = meta.get("_dd.appsec.s." + address)
        if payload is not None:
            return payload
    return


@rfc("https://docs.google.com/document/d/1OCHPBCAErOL2FhLl64YAHB8woDyq66y5t-JGolxdf1Q/edit#heading=h.bth088vsbjrz")
@scenarios.appsec_api_security_with_sampling
@features.api_security_configuration
class Test_API_Security_Sampling_Rate:
    """Test API Security - Default 0.1 Sampling on Request Headers Schema"""

    N = 20  # square root of number of requests

    def setup_sampling_rate(self):
        self.all_requests = [
            weblog.get(
                f"/tag_value/api_match_AS001/200?{''.join(random.choices(string.ascii_letters, k=16))}={random.randint(1<<31, (1<<32)-1)}"
            )
            for _ in range(self.N ** 2)
        ]

    @irrelevant(
        context.library not in ("nodejs", "python"), reason="New sampling algorithm tests have been implemented"
    )
    def test_sampling_rate(self):
        """can provide request header schema"""
        N = self.N
        assert all(r.status_code == 200 for r in self.all_requests)
        s = sum(get_schema(r, "req.headers") is not None for r in self.all_requests)
        # check result is in at most 4 standard deviations from expected
        # (assuming 99.98% confidence interval)
        # standard deviation is N * 0.3 for 0.1 sampling rate
        diff = abs(s / N - N * 0.1) / 0.3
        logger.info(
            f"API SECURITY SAMPLING RESULT: got {s} requests with api sec schemas out of {N**2} requests, expecting {int(N**2 * 0.1)}"
        )
        logger.info(f"API SECURITY SAMPLING RESULT: diff is {diff:.2f} standard deviations")
        assert diff <= 4.0, "sampling rate is not 0.1"


@rfc("https://docs.google.com/document/d/1PYoHms9PPXR8V_5_T5-KXAhoFDKQYA8mTnmS12xkGOE")
@scenarios.appsec_api_security_with_sampling
@features.api_security_configuration
class Test_API_Security_Sampling_Different_Endpoints:
    """Test API Security - with different endpoints"""

    def setup_sampling_delay(self):
        time.sleep(5)
        self.request1 = weblog.get("/api_security/sampling/200")
        self.request2 = weblog.get("/sample_rate_route/1")
        self.all_requests = [weblog.get("/api_security/sampling/200") for _ in range(10)]

    def test_sampling_delay(self):

        assert self.request1.status_code == 200
        schema1 = get_schema(self.request1, "req.headers")
        assert schema1 is not None

        assert self.request2.status_code == 200
        schema2 = get_schema(self.request2, "req.headers")
        assert schema2 is not None

        assert all(r.status_code == 200 for r in self.all_requests)
        assert all(get_schema(r, "req.headers") is None for r in self.all_requests)


@rfc("https://docs.google.com/document/d/1PYoHms9PPXR8V_5_T5-KXAhoFDKQYA8mTnmS12xkGOE")
@scenarios.appsec_api_security_with_sampling
@features.api_security_configuration
class Test_API_Security_Sampling_Different_Paths:
    """Test API Security - same endpoints but different paths"""

    def setup_sampling_delay(self):
        # Wait for 5s to avoid other tests calling same endpoints
        time.sleep(5)
        self.request1 = weblog.get("/sample_rate_route/11")
        self.all_requests = [weblog.get(f"/sample_rate_route/{i}") for i in range(10)]

    def test_sampling_delay(self):

        assert self.request1.status_code == 200
        schema1 = get_schema(self.request1, "req.headers")
        assert schema1 is not None

        assert all(r.status_code == 200 for r in self.all_requests)
        assert all(get_schema(r, "req.headers") is None for r in self.all_requests)


@rfc("https://docs.google.com/document/d/1PYoHms9PPXR8V_5_T5-KXAhoFDKQYA8mTnmS12xkGOE")
@scenarios.appsec_api_security_with_sampling
@features.api_security_configuration
class Test_API_Security_Sampling_Different_Status:
    """Test API Security - Same endpoint and different status"""

    def setup_sampling_delay(self):
        # Wait for 5s to avoid other tests calling same endpoints
        time.sleep(5)
        self.request1 = weblog.get("/api_security/sampling/200")
        self.request2 = weblog.get("/api_security/sampling/201")
        self.all_requests = [weblog.get("/api_security/sampling/201") for _ in range(10)]

    def test_sampling_delay(self):
        """can provide request header schema"""

        assert self.request1.status_code == 200
        schema1 = get_schema(self.request1, "req.headers")
        assert schema1 is not None

        assert self.request2.status_code == 201
        schema2 = get_schema(self.request2, "req.headers")
        assert schema2 is not None

        assert all(r.status_code == 201 for r in self.all_requests)
        assert all(get_schema(r, "req.headers") is None for r in self.all_requests)


@rfc("https://docs.google.com/document/d/1PYoHms9PPXR8V_5_T5-KXAhoFDKQYA8mTnmS12xkGOE")
@scenarios.appsec_api_security_with_sampling
@features.api_security_configuration
class Test_API_Security_Sampling_With_Delay:
    """Test API Security - Same endpoint with delay"""

    def setup_sampling_delay(self):
        # Wait for 5s to avoid other tests calling same endpoints
        time.sleep(5)
        self.request1 = weblog.get("/sample_rate_route/1")
        self.request2 = weblog.get("/sample_rate_route/1")
        time.sleep(4)  # Delay is set to 3s via the env var DD_API_SECURITY_SAMPLE_DELAY
        self.request3 = weblog.get("/sample_rate_route/1")

    def test_sampling_delay(self):
        """can provide request header schema"""

        assert self.request1.status_code == 200
        schema1 = get_schema(self.request1, "req.headers")
        assert schema1 is not None

        assert self.request2.status_code == 200
        schema2 = get_schema(self.request2, "req.headers")
        assert schema2 is None

        assert self.request3.status_code == 200
        schema3 = get_schema(self.request3, "req.headers")
        assert schema3 is not None
