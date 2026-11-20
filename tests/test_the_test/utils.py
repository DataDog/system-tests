import ast
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock

from utils import logger, pytest
from utils._context.containers import TestedContainer as _TestedContainer


def get_scenario_map() -> dict[str, list[str]]:
    _execute_system_tests(scenario_map=True, print_stdout=False)
    with Path("logs_mock_the_test/scenarios.json").open(encoding="utf-8") as f:
        return json.load(f)


def run_system_tests(
    scenario: str = "MOCK_THE_TEST",
    test_path: str | None = None,
    *,
    verbose: bool = False,
    forced_test: str | None = None,
    use_xdist: bool = False,
    xfail_strict: bool = False,
    env: dict[str, str] | None = None,
    expected_return_code: int = 0,
) -> dict[str, dict]:
    _execute_system_tests(
        scenario=scenario,
        test_path=test_path,
        verbose=verbose,
        forced_test=forced_test,
        use_xdist=use_xdist,
        xfail_strict=xfail_strict,
        env=env,
        expected_return_code=expected_return_code,
    )

    return read_junit_report(scenario or "DEFAULT")


def read_junit_suite_properties(scenario: str) -> dict[str, str]:
    root = ET.parse(f"logs_{scenario.lower()}/reportJunit.xml").getroot()  # noqa: S314
    return {prop.attrib["name"]: prop.attrib["value"] for prop in root.findall("testsuite/properties/property")}


def read_junit_report(scenario: str, weblog_variant: str = "spring") -> dict[str, dict]:
    """Read the junit report of ``scenario``, and return its test cases by pytest nodeid.

    Tests declared as irrelevant are not in the junit report.
    """
    root = ET.parse(f"logs_{scenario.lower()}/reportJunit.xml").getroot()  # noqa: S314

    result: dict[str, dict] = {}
    for testcase in root.iter("testcase"):
        properties = {prop.attrib["name"]: prop.attrib["value"] for prop in testcase.iter("property")}
        nodeid = _junit_name_to_nodeid(testcase.attrib["name"], weblog_variant)
        result[nodeid] = {
            "outcome": properties.get("dd_tags[systest.case.outcome]"),
            "declaration": properties.get("dd_tags[systest.case.declaration]"),
            "declaration_details": properties.get("dd_tags[systest.case.declarationDetails]"),
            "features": ast.literal_eval(properties.get("dd_tags[systest.case.feature_ids]") or "[]"),
            "properties": properties,
        }

    return result


def _junit_name_to_nodeid(name: str, weblog_variant: str) -> str:
    """Convert a junit name (tests.dir.test_file.Class.test_method[params, weblog]) into a pytest nodeid"""
    name, _, params = name.partition("[")
    params_list = params.removesuffix("]").split(", ")
    assert params_list[-1] == weblog_variant, f"Unexpected weblog suffix in junit name {name}[{params}"
    params_list.pop()

    parts = name.split(".")
    for i in range(1, len(parts)):
        path = "/".join(parts[:i]) + ".py"
        if Path(path).is_file():
            nodeid = "::".join([path, *parts[i:]])
            break
    else:
        raise ValueError(f"Can't find the test file of junit name {name}")

    return f"{nodeid}[{', '.join(params_list)}]" if params_list else nodeid


def _execute_system_tests(
    scenario: str = "MOCK_THE_TEST",
    test_path: str | None = None,
    *,
    verbose: bool = False,
    forced_test: str | None = None,
    use_xdist: bool = False,
    xfail_strict: bool = False,
    scenario_map: bool = False,
    env: dict[str, str] | None = None,
    print_stdout: bool = False,
    expected_return_code: int = 0,
):
    cmd_parts = ["./run.sh"]

    if scenario:
        cmd_parts.append(scenario)
    if test_path:
        cmd_parts.append(test_path)
    if verbose:
        cmd_parts.append("-v")
    if forced_test:
        cmd_parts.extend(["-F", forced_test])
    if xfail_strict:
        cmd_parts.extend(["-o", "xfail_strict=True"])
    if use_xdist:
        cmd_parts.extend(["-n=4"])
    if scenario_map:
        cmd_parts.extend(["--collect-only", "--scenario-report"])

    logger.info(" ".join(cmd_parts))
    result = subprocess.run(cmd_parts, capture_output=True, text=True, check=False, env=env)

    if print_stdout:
        logger.info(result.stdout)
    assert result.returncode == expected_return_code, f"Command failed with return code {result.returncode}"


def extra_hosts_at_start(monkeypatch: pytest.MonkeyPatch, container: _TestedContainer) -> dict[str, str] | None:
    """Start ``container`` without docker, and return the extra hosts it would be started with."""
    started_with: list[dict[str, str] | None] = []

    def fake_start(self: _TestedContainer, network) -> None:  # noqa: ANN001, ARG001
        started_with.append(self.extra_hosts)

    monkeypatch.setattr(_TestedContainer, "start", fake_start)
    container.start(MagicMock())
    return started_with[0]
