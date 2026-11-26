"""Validate environment variables and write them to param.env.

Called by .system_tests_param_base in main.yml. The caller (before_script) is
responsible for exporting the variables into the environment before this script runs.
"""

from __future__ import annotations

import json
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
    """Comma-separated lowercase identifiers allowing hyphens and dots, e.g. 'flask,django-realworld,apache-mod-8.0'."""
    errors = []
    for item in (i.strip() for i in value.split(",")):
        if item and not re.match(r"^[a-z][a-z0-9._-]*$", item):
            errors.append(
                _error(name, item, "expected comma-separated lowercase identifiers (e.g. 'flask,apache-mod-8.0')")
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


def validate_int(name: str, value: str) -> list[str]:
    """Must be an integer, e.g. '-1' or '900'."""
    if not re.match(r"^-?[0-9]+$", value):
        return [_error(name, value, "expected an integer")]
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


def validate_library_weblog_scenarios(name: str, value: str) -> list[str]:
    """JSON object {library: {weblog: [scenario or group, ...]}}.

    E.g. '{"python": {"flask-poc": ["DEFAULT", "appsec"]}}'.
    """
    expected = 'expected a JSON object like {"python": {"flask-poc": ["DEFAULT"]}}'
    try:
        data = json.loads(value)
    except json.JSONDecodeError as e:
        return [_error(name, value, f"invalid JSON ({e}), {expected}")]

    if not isinstance(data, dict):
        return [_error(name, value, expected)]

    errors = []
    for library, weblogs in data.items():
        if not re.match(r"^[a-z][a-z0-9_]*$", library):
            errors.append(_error(name, library, "invalid library name"))
        if not isinstance(weblogs, dict):
            errors.append(_error(name, library, f"weblogs must be a JSON object, {expected}"))
            continue
        for weblog, scenarios in weblogs.items():
            # dots are allowed: e.g. apache-mod-8.0, python3.12
            if not re.match(r"^[a-z][a-z0-9._-]*$", weblog):
                errors.append(_error(name, weblog, "invalid weblog name"))
            if not isinstance(scenarios, list):
                errors.append(_error(name, weblog, f"scenarios must be a list, {expected}"))
                continue
            for entry in scenarios:
                if not isinstance(entry, str) or not re.match(r"^([A-Z][A-Z0-9_]*|[a-z][a-z0-9_]*)$", entry):
                    errors.append(
                        _error(name, str(entry), "expected a scenario (e.g. DEFAULT) or a scenario group (e.g. appsec)")
                    )
    return errors


def validate_target_branch_map(name: str, value: str) -> list[str]:
    """JSON object {library or "agent": branch}, e.g. '{"python": "my-branch", "agent": "7.70.x"}'.

    Only the format is checked here: which libraries can have a target branch is checked by build_pipeline.py.
    """
    expected = 'expected a JSON object like {"python": "my-branch"}'
    try:
        data = json.loads(value)
    except json.JSONDecodeError as e:
        return [_error(name, value, f"invalid JSON ({e}), {expected}")]

    if not isinstance(data, dict):
        return [_error(name, value, expected)]

    errors = []
    for library, branch in data.items():
        if not re.match(r"^[a-z][a-z0-9_]*$", library):
            errors.append(_error(name, library, "invalid library name"))
        # same pattern as TARGET_BRANCH_PATTERN in build_pipeline.py: no character GitLab would expand ($)
        if not isinstance(branch, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/+-]*", branch):
            errors.append(_error(name, str(branch), f"invalid branch name for {library}"))
    return errors


# Variables written to param.env, read by build_pipeline.py (see its MERGED_LIST_VARIABLES and OVERRIDE_VARIABLES)
CHECKS: list[tuple[str, object]] = [
    ("LIBRARIES", validate_space_lower),
    ("SCENARIOS", validate_comma_upper),
    ("SCENARIO_GROUPS", validate_comma_lower),
    ("WEBLOGS", validate_comma_lower_hyphen),
    ("LIBRARY_WEBLOG_SCENARIOS", validate_library_weblog_scenarios),
    ("EXCLUDED_SCENARIOS", validate_comma_upper),
    ("FORCE_EXECUTE", None),  # pytest node IDs are too complex to validate by format
    ("SYSTEM_TESTS_PARAMETRIC_JOB_COUNT", validate_positive_int),
    ("SYSTEM_TESTS_PARAMETRIC_WORKERS", validate_positive_int),
    ("SYSTEM_TESTS_DESIRED_EXECUTION_TIME", validate_int),
    ("SYSTEM_TESTS_ENDTOEND_JOB_COUNT", validate_int),
    ("SYSTEM_TESTS_PUSH_TO_TEST_OPTIMIZATION", validate_bool),
    ("SYSTEM_TESTS_SKIP_EMPTY_SCENARIO", validate_bool),
    ("BINARIES_ARTIFACTS", validate_semicolon_nonempty),
    ("BINARIES_ARTIFACT_PATH", validate_path),
    ("SYSTEM_TESTS_PIPELINE_START_TIME", validate_positive_int),
    ("SYSTEM_TESTS_E2E_DEV_MODE", validate_bool),
    ("SYSTEM_TESTS_E2E_TARGET_BRANCH_MAP", validate_target_branch_map),
]

# JSON values: dotenv reports do not support multiline values, they are written on a single line
JSON_VARIABLES = ("LIBRARY_WEBLOG_SCENARIOS", "SYSTEM_TESTS_E2E_TARGET_BRANCH_MAP")

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
                if name in JSON_VARIABLES:
                    value = json.dumps(json.loads(value), separators=(",", ":"))
                f.write(f"{name}={value}\n")

    with open(PARAM_ENV) as f:
        print(f.read(), end="")  # noqa: T201


if __name__ == "__main__":
    main()
