"""Test that dd-trace works correctly without OpenFeature SDK installed.

This test validates the fix for https://github.com/DataDog/dd-trace-js/issues/6986
which ensures that dd-trace users who don't use OpenFeature don't encounter
peer dependency errors or runtime failures.
"""

from utils import weblog, scenarios, features


@scenarios.default
@features.feature_flags_exposures
class Test_DDTrace_Without_OpenFeature:
    """Test dd-trace functionality when OpenFeature SDK is not installed.

    This validates that:
    1. dd-trace initializes successfully without OpenFeature
    2. Basic tracing functionality works
    3. The application doesn't crash due to missing OpenFeature dependencies
    """

    def setup_ddtrace_works_without_openfeature(self):
        """Verify the root endpoint works (proves dd-trace initialized)."""
        self.root_response = weblog.get("/")

    def test_ddtrace_works_without_openfeature(self):
        """Test that dd-trace initializes and works without OpenFeature installed."""
        # The main test is that the weblog starts at all - if dd-trace fails to
        # initialize due to missing OpenFeature, the weblog won't respond
        assert self.root_response.status_code == 200, (
            f"Root endpoint failed with status {self.root_response.status_code}: {self.root_response.text}"
        )
