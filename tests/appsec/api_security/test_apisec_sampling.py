from utils import (
    context,
    features,
    interfaces,
    irrelevant,
    rfc,
    scenarios,
    weblog,
    logger,
)

import random
import string
import time


def get_schema(request, address):
    """Get api security schema from spans"""
    for _, _, span in interfaces.library.get_spans(request):
        meta = span.get("meta", {})
        payload = meta.get("_dd.appsec.s." + address)
        if payload is not None:
            return payload
    return None


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
            for _ in range(self.N**2)
        ]

    @irrelevant(
        context.library not in ("nodejs", "python", "ruby"), reason="New sampling algorithm tests have been implemented"
    )
    def test_sampling_rate(self):
        """Can provide request header schema"""
        n = self.N
        assert all(r.status_code == 200 for r in self.all_requests)
        s = sum(get_schema(r, "req.headers") is not None for r in self.all_requests)
        # check result is in at most 4 standard deviations from expected
        # (assuming 99.98% confidence interval)
        # standard deviation is N * 0.3 for 0.1 sampling rate
        diff = abs(s / n - n * 0.1) / 0.3
        logger.info(
            f"API SECURITY SAMPLING RESULT: got {s} requests with api sec schemas out of {n**2} requests, expecting {int(n**2 * 0.1)}"
        )
        logger.info(f"API SECURITY SAMPLING RESULT: diff is {diff:.2f} standard deviations")
        assert diff <= 4.0, "sampling rate is not 0.1"


@rfc("https://docs.google.com/document/d/1PYoHms9PPXR8V_5_T5-KXAhoFDKQYA8mTnmS12xkGOE")
@scenarios.appsec_api_security_with_sampling
@features.api_security_configuration
class Test_API_Security_Sampling_Different_Endpoints:
    """Test API Security - with different endpoints"""

    def setup_sampling_delay(self):
        with weblog.get_session() as session:
            self.request1 = session.get("/api_security/sampling/200")
            self.request2 = session.get("/api_security_sampling/1")
            self.all_requests = [session.get("/api_security/sampling/200") for _ in range(10)]

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
        # Wait for 10s to avoid other tests calling same endpoints
        time.sleep(10)
        with weblog.get_session() as session:
            self.request1 = session.get("/api_security_sampling/11")
            self.all_requests = [session.get(f"/api_security_sampling/{i}") for i in range(10)]

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
        with weblog.get_session() as session:
            self.request1 = session.get("/api_security/sampling/200")
            self.request2 = session.get("/api_security/sampling/201")
            self.all_requests = [session.get("/api_security/sampling/201") for _ in range(10)]

    def test_sampling_delay(self):
        """Can provide request header schema"""

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
        # Wait for 15s to avoid other tests calling same endpoints
        time.sleep(15)
        with weblog.get_session() as session:
            self.request1 = session.get("/api_security_sampling/30")
            self.request2 = session.get("/api_security_sampling/30")
            time.sleep(4)  # Delay is set to 3s via the env var DD_API_SECURITY_SAMPLE_DELAY
            self.request3 = session.get("/api_security_sampling/30")

    def test_sampling_delay(self):
        """Can provide request header schema"""

        assert self.request1.status_code == 200
        assert self.request2.status_code == 200

        schema1 = get_schema(self.request1, "req.headers")
        schema2 = get_schema(self.request2, "req.headers")

        assert (schema1 is None) != (schema2 is None), "Expected exactly one request to be sampled"

        assert self.request3.status_code == 200
        schema3 = get_schema(self.request3, "req.headers")
        assert schema3 is not None
