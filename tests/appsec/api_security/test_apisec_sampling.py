from utils import (
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
class Test_API_Security_sampling:
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
        context.library not in ["nodejs"], reason="RFC is deprecated by a newer RFC. New tests will be implemented"
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
