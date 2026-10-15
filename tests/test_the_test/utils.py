import json
import subprocess
from pathlib import Path

from utils import logger


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

    scenario = scenario or "DEFAULT"
    with open(f"logs_{scenario.lower()}/feature_parity.json", encoding="utf-8") as f:
        report = json.load(f)

    return {test["path"]: test for test in report["tests"]}


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
