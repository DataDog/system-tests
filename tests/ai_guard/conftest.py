import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Mark all ai_guard tests as xfail when generating cassettes."""
    if getattr(config.option, "generate_cassettes", False):
        for item in items:
            item.add_marker(
                pytest.mark.xfail(
                    reason="Generating cassettes - test assertions are not evaluated",
                    strict=False,
                )
            )
