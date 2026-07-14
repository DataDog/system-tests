"""Source-neutral helpers for end-to-end feature flag evaluation."""

from utils import HttpResponse, weblog

from .fixtures import JSON


def evaluate_flag(
    flag_key: str,
    *,
    targeting_key: str = "user-1",
    attributes: JSON | None = None,
    variation_type: str = "STRING",
    default_value: object = "default",
) -> HttpResponse:
    return weblog.post(
        "/ffe",
        json={
            "flag": flag_key,
            "variationType": variation_type,
            "defaultValue": default_value,
            "targetingKey": targeting_key,
            "attributes": attributes or {},
        },
    )
