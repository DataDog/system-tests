from utils import (
    coverage,
    features,
    interfaces,
    rfc,
    scenarios,
    weblog,
)

import random
import string
import pytest


@pytest.fixture(name="printer")
def printer(request):
    """Pytest plugin to print test progress steps in verbose mode."""
    terminal_reporter = request.config.pluginmanager.getplugin("terminalreporter")
    if terminal_reporter is not None:  # pragma: no branch
        return terminal_reporter.write_line
    return lambda msg: None


def get_schema(request, address):
    """get api security schema from spans"""
    for _, _, span in interfaces.library.get_spans(request):
        meta = span.get("meta", {})
        payload = meta.get("_dd.appsec.s." + address)
        if payload is not None:
            return payload
    return


@rfc("https://docs.google.com/document/d/1OCHPBCAErOL2FhLl64YAHB8woDyq66y5t-JGolxdf1Q/edit#heading=h.bth088vsbjrz")
@coverage.basic
@scenarios.appsec_api_security_with_sampling
@features.api_security_schemas
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

    def test_sampling_rate(self, printer):
        """can provide request header schema"""
        N = self.N
        assert all(r.status_code == 200 for r in self.all_requests)
        self.s = sum(get_schema(r, "req.headers") is not None for r in self.all_requests)
        # check result is in at most 4 standard deviations from expected
        # (assuming 99.98% confidence interval)
        # standard deviation is N * 0.3 for 0.1 sampling rate
        self.diff = abs(self.s / N - N * 0.1) / 0.3
        self.log_fun = printer
        assert (N ** 2) * 0.1 - 1.2 * N <= self.s <= (N ** 2) * 0.1 + 1.2 * N, "sampling rate is not 0.1"

    def teardown_method(self):
        """add result visibility to pytest report"""
        self.log_fun(
            f"  got {self.s} requests with api sec schemas out of {self.N**2} requests, expecting {int(self.N**2 * 0.1)}"
        )
        if self.diff:
            self.log_fun(f"  diff is {self.diff:.2f} standard deviations")
