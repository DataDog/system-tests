import os
from typing import Any, Literal
import pytest


def check_and_get_api_key(api_key_name: str, *, generate_cassettes: bool = False) -> str | None:
    if generate_cassettes:
        api_key = os.getenv(api_key_name)
        if not api_key:
            pytest.exit(f"{api_key_name} is required to generate cassettes", 1)
        return api_key
    else:
        return "<not-a-real-key>"


def find_event_tag(event: dict, tag: str) -> str | None:
    tags: list[str] = event["tags"]
    for t in tags:
        k, v = t.split(":")
        if k == tag:
            return v

    return None


def get_io_value_from_span_event(
    span_event: dict,
    kind: Literal["input", "output"],
    key: Literal["messages", "documents", "value"],
) -> list[dict[str, Any]]:
    meta = span_event["meta"]
    from_kind_directly = kind in meta

    return meta[kind][key] if from_kind_directly else meta[f"{kind}.{key}"]
