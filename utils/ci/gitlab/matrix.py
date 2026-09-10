"""Parsing for the per-library "configuration matrix" accepted by .system_tests_param.

Users extending `.system_tests_param` can set a `MATRIX` variable to override, on a
per-library basis, which scenarios/scenario groups/weblogs/excluded scenarios are used
when generating the child pipeline. It uses YAML flow-mapping syntax (a superset of JSON
that doesn't require quoted keys), e.g.:

    {python: {scenarios: [DEFAULT, FOO]}, python_lambda: {scenario_groups: tracer_release}}

Multi-valued fields must use `[...]` list syntax (bare commas without brackets are
ambiguous in YAML and would be parsed as extra keys).
"""

from __future__ import annotations

import yaml

ALLOWED_KEYS = ("scenarios", "scenario_groups", "weblogs", "excluded_scenarios")


def _normalize_value(key: str, value: object) -> str:
    if isinstance(value, list):
        return ",".join(str(item) for item in value)
    if isinstance(value, (str, int, float)):
        return str(value)
    raise ValueError(f"Invalid value for '{key}': expected a string or a list of strings, got {value!r}")


def parse_matrix(matrix: str) -> dict[str, dict[str, str]]:
    """Parse a MATRIX string into `{library: {field: "comma,separated,values"}}`.

    Returns an empty dict if *matrix* is empty/blank.
    Raises ValueError on malformed input (bad YAML, or unknown field names) and TypeError
    if the parsed YAML has the wrong shape (not a mapping of library -> mapping of field -> value).
    """

    matrix = matrix.strip()
    if not matrix:
        return {}

    try:
        parsed = yaml.safe_load(matrix)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid MATRIX value: not valid YAML: {e}") from e

    if not isinstance(parsed, dict):
        raise TypeError(f"Invalid MATRIX value: expected a mapping of library -> config, got {parsed!r}")

    result: dict[str, dict[str, str]] = {}

    for library, config in parsed.items():
        if not isinstance(library, str):
            raise TypeError(f"Invalid MATRIX value: library name {library!r} must be a string")

        if not isinstance(config, dict):
            raise TypeError(f"Invalid MATRIX value: config for library '{library}' must be a mapping, got {config!r}")

        normalized_config: dict[str, str] = {}
        for key, value in config.items():
            if key not in ALLOWED_KEYS:
                raise ValueError(
                    f"Invalid MATRIX value: unknown key '{key}' for library '{library}'. "
                    f"Allowed keys are: {', '.join(ALLOWED_KEYS)}"
                )
            normalized_config[key] = _normalize_value(key, value)

        result[library] = normalized_config

    return result
