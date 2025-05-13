import json
import os

from utils import logger


def run_system_tests(scenario="MOCK_THE_TEST", test_path=None, *, verbose=False, forced_test=None, xfail_strict=False):
    cmd_parts = ["./run.sh"]

    if scenario:
        cmd_parts.append(scenario)
    if test_path:
        cmd_parts.append(test_path)
    if verbose:
        cmd_parts.append("-v")
    if forced_test:
        cmd_parts.append(f"-F {forced_test}")
    if xfail_strict:
        cmd_parts.append("-o xfail_strict=True")

    cmd = " ".join(cmd_parts)
    logger.info(cmd)
    stream = os.popen(cmd)
    output = stream.read()

    logger.info(output)

    scenario = scenario if scenario else "DEFAULT"
    with open(f"logs_{scenario.lower()}/feature_parity.json", encoding="utf-8") as f:
        report = json.load(f)

    return {test["path"]: test for test in report["tests"]}
