import os
import pytest


def check_and_get_api_key(api_key_name: str, *, generate_cassettes: bool = False) -> str | None:
    if generate_cassettes:
        api_key = os.getenv(api_key_name)
        if not api_key:
            pytest.exit(f"{api_key_name} is required to generate cassettes", 1)
        return api_key
    else:
        return "<not-a-real-key>"
