"""Shared FFE Remote Config fixtures for system tests."""

from typing import Any


JSON = dict[str, Any]
VariationValue = str | bool | float | int


DEFAULT_VARIATION_VALUES: dict[str, dict[str, VariationValue]] = {
    "STRING": {"on": "on-value", "off": "off-value"},
    "BOOLEAN": {"on": True, "off": False},
    "NUMERIC": {"on": 1.5, "off": 0.0},
    "INTEGER": {"on": 42, "off": 0},
}


def make_ufc_fixture(
    flag_key: str,
    variant_key: str = "on",
    variation_type: str = "STRING",
    *,
    enabled: bool = True,
    allocation_key: str = "default-allocation",
    variation_values: dict[str, VariationValue] | None = None,
    observe_full_evaluation_data: bool | None = None,
) -> JSON:
    values = variation_values or DEFAULT_VARIATION_VALUES[variation_type]

    environment: JSON = {"name": "Test"}
    if observe_full_evaluation_data is not None:
        environment["observeFullEvaluationData"] = observe_full_evaluation_data

    return {
        "createdAt": "2024-04-17T19:40:53.716Z",
        "format": "SERVER",
        "environment": environment,
        "flags": {
            flag_key: {
                "key": flag_key,
                "enabled": enabled,
                "variationType": variation_type,
                "variations": {key: {"key": key, "value": value} for key, value in values.items()},
                "allocations": [
                    {
                        "key": allocation_key,
                        "rules": [],
                        "splits": [{"variationKey": variant_key, "shards": []}],
                        "doLog": True,
                    }
                ],
            }
        },
    }


def make_exposure_ufc_fixture(
    flag_key: str,
    variant_key: str = "variant-a",
    allocation_key: str = "default-allocation",
) -> JSON:
    return make_ufc_fixture(
        flag_key,
        variant_key,
        allocation_key=allocation_key,
        variation_values={"variant-a": "value-a", "variant-b": "value-b"},
    )
