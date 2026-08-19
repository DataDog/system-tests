from collections.abc import Generator
from typing import Any
import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> Generator[None, Any, None]:
    """When generating cassettes, don't let setup/assertion failures fail the run."""
    outcome = yield
    if item.config.option.generate_cassettes and call.when in ("setup", "call") and call.excinfo is not None:
        report = outcome.get_result()
        report.outcome = "skipped"
        current_filename, lineno, _ = item.location
        report.longrepr = (current_filename, lineno, "Generating cassettes - test assertions are not evaluated")
