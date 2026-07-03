"""Validate environment variables and write them to param.env.

Called by .system_tests_param_base in main.yml. The caller (before_script) is
responsible for exporting the variables into the environment before this script runs.
"""

from __future__ import annotations

import os
import re
import sys


def _error(name: str, value: str, msg: str) -> str:
    return f"❌ {name}: '{value}' — {msg}"


def validate_space_lower(name: str, value: str) -> list[str]:
    """Space-separated lowercase identifiers, e.g. 'python java_otel'."""
    errors = []
    for item in value.split():
        if not re.match(r"^[a-z][a-z0-9_]*$", item):
            errors.append(
                _error(name, item, "expected space-separated lowercase identifiers (e.g. 'python java_otel')")
            )
    return errors


def validate_comma_upper(name: str, value: str) -> list[str]:
    """Comma-separated uppercase identifiers, e.g. 'DEFAULT,PARAMETRIC'."""
    errors = []
    for item in (i.strip() for i in value.split(",")):
        if item and not re.match(r"^[A-Z][A-Z0-9_]*$", item):
            errors.append(
                _error(name, item, "expected comma-separated uppercase identifiers (e.g. 'DEFAULT,PARAMETRIC')")
            )
    return errors


def validate_comma_lower(name: str, value: str) -> list[str]:
    """Comma-separated lowercase identifiers, e.g. 'all,appsec'."""
    errors = []
    for item in (i.strip() for i in value.split(",")):
        if item and not re.match(r"^[a-z][a-z0-9_]*$", item):
            errors.append(_error(name, item, "expected comma-separated lowercase identifiers (e.g. 'all,appsec')"))
    return errors


def validate_comma_lower_hyphen(name: str, value: str) -> list[str]:
    """Comma-separated lowercase identifiers allowing hyphens, e.g. 'flask,django-realworld'."""
    errors = []
    for item in (i.strip() for i in value.split(",")):
        if item and not re.match(r"^[a-z][a-z0-9_-]*$", item):
            errors.append(
                _error(name, item, "expected comma-separated lowercase identifiers (e.g. 'flask,django-realworld')")
            )
    return errors


def validate_bool(name: str, value: str) -> list[str]:
    """Must be 'true' or 'false'."""
    if value not in ("true", "false"):
        return [_error(name, value, "expected 'true' or 'false'")]
    return []


def validate_positive_int(name: str, value: str) -> list[str]:
    """Must be a positive integer."""
    if not re.match(r"^[1-9][0-9]*$", value):
        return [_error(name, value, "expected a positive integer")]
    return []


def validate_path(name: str, value: str) -> list[str]:
    """Must be a valid relative path."""
    if not re.match(r"^[a-zA-Z0-9_][a-zA-Z0-9_./-]*$", value):
        return [_error(name, value, "expected a valid relative path")]
    return []


def validate_semicolon_nonempty(name: str, value: str) -> list[str]:
    """Semicolon-separated non-empty entries, e.g. job names."""
    errors = []
    for item in (i.strip() for i in value.split(";")):
        if not item:
            errors.append(_error(name, value, "empty entry found — expected semicolon-separated non-empty job names"))
    return errors


CHECKS: list[tuple[str, object]] = [
    ("LIBRARIES", validate_space_lower),
    ("SCENARIOS", validate_comma_upper),
    ("SCENARIO_GROUPS", validate_comma_lower),
    ("WEBLOGS", validate_comma_lower_hyphen),
    ("EXCLUDED_SCENARIOS", validate_comma_upper),
    ("FORCE_EXECUTE", None),  # pytest node IDs are too complex to validate by format
    ("SYSTEM_TESTS_PARAMETRIC_JOB_COUNT", validate_positive_int),
    ("SYSTEM_TESTS_PUSH_TO_TEST_OPTIMIZATION", validate_bool),
    ("SYSTEM_TESTS_DOCKER_AUTH", validate_bool),
    ("SYSTEM_TESTS_SKIP_EMPTY_SCENARIO", validate_bool),
    ("BINARIES_ARTIFACTS", validate_semicolon_nonempty),
    ("BINARIES_ARTIFACT_PATH", validate_path),
]

PARAM_ENV = "param.env"


def main() -> None:
    errors: list[str] = []

    for name, validator in CHECKS:
        value = os.environ.get(name, "")
        if value and validator is not None:
            errors.extend(validator(name, value))  # type: ignore[operator]

    if errors:
        for e in errors:
            print(e, file=sys.stderr)  # noqa: T201
        sys.exit(1)

    with open(PARAM_ENV, "w") as f:
        for name, _ in CHECKS:
            value = os.environ.get(name, "")
            if value:
                f.write(f"{name}={value}\n")

    with open(PARAM_ENV) as f:
        print(f.read(), end="")  # noqa: T201


if __name__ == "__main__":
    main()
