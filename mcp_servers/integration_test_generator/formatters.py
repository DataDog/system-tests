"""Helper functions for formatting template data."""


def format_excluded_metrics(integration_name: str, excluded_metrics: list[str] | None) -> str:
    """Format excluded metrics section.
    
    Args:
        integration_name: Name of the integration
        excluded_metrics: List of metrics to exclude (optional)
    
    Returns:
        Formatted excluded metrics string
    """
    if excluded_metrics:
        excluded_metrics_formatted = ",\n    ".join([f'"{m}"' for m in excluded_metrics])
        return f"""
# Exclude metrics that require specific setup or sustained activity
_EXCLUDED_{integration_name.upper()}_METRICS = {{
    {excluded_metrics_formatted}
}}
"""
    else:
        return f"_EXCLUDED_{integration_name.upper()}_METRICS: set[str] = set()"


def format_smoke_operations(operations: list[str]) -> str:
    """Format smoke test operations.
    
    Args:
        operations: List of operation strings
    
    Returns:
        Formatted operations string
    """
    return "\n        ".join(operations)


def format_expected_metrics(metrics: list[str]) -> str:
    """Format expected metrics list.
    
    Args:
        metrics: List of metric names
    
    Returns:
        Formatted metrics string
    """
    return ",\n            ".join([f'"{m}"' for m in metrics])

