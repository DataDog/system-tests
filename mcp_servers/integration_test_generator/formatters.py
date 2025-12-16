"""Helper functions for formatting template data."""


def format_excluded_metrics(integration_name: str, excluded_metrics: list[str] | None) -> str:
    """Format excluded metrics section."""
    if excluded_metrics:
        excluded_metrics_formatted = ",\n    ".join([f'"{m}"' for m in excluded_metrics])
        return f"""
# Exclude metrics that require specific setup or sustained activity
_EXCLUDED_{integration_name.upper()}_METRICS = {{
    {excluded_metrics_formatted}
}}
"""
    return f"_EXCLUDED_{integration_name.upper()}_METRICS: set[str] = set()"


def format_smoke_operations(operations: list[str]) -> str:
    """Format smoke test operations."""
    return "\n        ".join(operations)


def format_expected_metrics(metrics: list[str]) -> str:
    """Format expected metrics list."""
    return ",\n            ".join([f'"{m}"' for m in metrics])
