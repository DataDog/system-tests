"""Detect the `datadog/system-tests` base image a weblog Dockerfile builds FROM.

Deliberately stdlib-only (no `utils` package, no venv) so `wait_for_base_image.py` can
import it as a plain CI step before the runner virtualenv is built.
"""

import re

# Match a `FROM [--flag ...] datadog/system-tests:<tag>` on ANY line: case-insensitive,
# tolerant of flags like `--platform=linux/amd64`, and of multi-stage Dockerfiles where the
# datadog base is a later stage (non-datadog FROM lines simply don't match the literal repo).
_FROM_DATADOG_BASE = re.compile(
    r"^\s*FROM\s+(?:--\S+\s+)*(datadog/system-tests:\S+)",
    re.IGNORECASE | re.MULTILINE,
)


def base_image_ref(dockerfile_text: str) -> str | None:
    """Return the `datadog/system-tests:<tag>` reference the Dockerfile builds FROM, or None."""
    match = _FROM_DATADOG_BASE.search(dockerfile_text)
    return match.group(1) if match else None
