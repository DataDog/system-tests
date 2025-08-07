import json
import subprocess

from utils import logger


def run_system_tests(
    scenario="MOCK_THE_TEST",
    test_path=None,
    *,
    verbose=False,
    forced_test=None,
    xfail_strict=False,
    env: dict[str, str] | None = None,
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

    logger.info(" ".join(cmd_parts))
    result = subprocess.run(cmd_parts, capture_output=True, text=True, check=False, env=env)

    logger.info(result.stdout)
    assert result.returncode == expected_return_code, f"Command failed with return code {result.returncode}"

    scenario = scenario if scenario else "DEFAULT"
    with open(f"logs_{scenario.lower()}/feature_parity.json", encoding="utf-8") as f:
        report = json.load(f)

    return {test["path"]: test for test in report["tests"]}
