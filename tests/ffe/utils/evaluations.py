"""Feature-flag evaluation event extraction helpers."""

import hashlib
from typing import Any, cast


JSON = dict[str, Any]
EVP_FLAGEVALUATIONS_PATH = "/api/v2/flagevaluation"


def _targeting_key_matches(actual: object, expected: str) -> bool:
    hashed = f"sha256_{hashlib.sha256(expected.encode()).hexdigest()}"
    return actual in (expected, hashed)


def evaluation_events_from_data(
    data: JSON,
    flag_keys: set[str] | None = None,
    targeting_key: str | None = None,
) -> list[JSON]:
    """Return evaluation events matching an optional flag set and subject."""
    if data.get("path") != EVP_FLAGEVALUATIONS_PATH:
        return []

    request = data.get("request")
    if not isinstance(request, dict):
        return []
    content = request.get("content")
    if not isinstance(content, dict):
        return []
    events = content.get("flagEvaluations")
    if not isinstance(events, list):
        return []

    results: list[JSON] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        flag = event.get("flag")
        flag_key = flag.get("key") if isinstance(flag, dict) else None
        if flag_keys is not None and flag_key not in flag_keys:
            continue
        if targeting_key is not None and not _targeting_key_matches(event.get("targeting_key"), targeting_key):
            continue
        results.append(cast("JSON", event))
    return results
