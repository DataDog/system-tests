"""Values copied into the JUnit property ``dd_tags[test.parameters]``.

That property is the Test Optimization fingerprint. A component version changes on every dev build, so it stays
out of the fingerprint. The caller still publishes the full value as a ``systest.suite.context`` tag.
"""


def fingerprint_parameters(properties: dict[str, str | dict[str, str]]) -> dict[str, str | dict[str, str]]:
    """Drop component versions from the fingerprint.

    ``installed_language_runtime`` is a plain string and stays: it identifies the runtime under test.
    ``agent`` is a plain version string, so the whole entry stays out. A nested ``version`` key stays out too.
    """
    parameters: dict[str, str | dict[str, str]] = {}
    for key, value in properties.items():
        if key == "agent":
            continue
        if isinstance(value, dict):
            kept = {name: item for name, item in value.items() if name != "version"}
            if kept:
                parameters[key] = kept
        else:
            parameters[key] = value
    return parameters
