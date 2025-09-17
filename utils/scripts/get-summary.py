import argparse
from collections import defaultdict
from enum import StrEnum
import json
import logging
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)]
)

REPORT_FILENAME = "reportJunit.xml"


class PropertyName(StrEnum):
    # testsuite
    WEBLOG = "dd_tags[systest.suite.context.weblog_variant]"
    SCENARIO = "dd_tags[systest.suite.context.scenario]"

    # testcase
    CODEOWNERS = "test.codeowners"
    OUTCOME = "dd_tags[systest.case.outcome]"


class Outcome(StrEnum):
    passed = "passed"
    failed = "failed"
    skipped = "skipped"
    error = "error"
    xfailed = "xfailed"
    xpassed = "xpassed"


class Test:
    def __init__(self, nodeid: str, outcome: str, scenario: str, weblog: str, owners: list[str]):
        self.nodeid = nodeid
        self.outcome = Outcome(outcome)
        self.scenario = scenario
        self.weblog = weblog
        self.owners = owners


class Summary:
    def __init__(self):
        self.tests: list[Test] = []
        self.tests_by_outcome: dict[Outcome, list[Test]] = defaultdict(list)
        self.failures: dict[str, list[Test]] = {}

    def add_test(self, test: Test) -> None:
        self.tests.append(test)
        self.tests_by_outcome[test.outcome].append(test)

        if test.outcome == Outcome.failed:
            for owner in test.owners:
                if owner not in self.failures:
                    self.failures[owner] = []
                self.failures[owner].append(test)

    def get_count(self, outcome: Outcome) -> int:
        return len(self.tests_by_outcome[outcome])

    def get_markdown(self) -> str:
        result: list[str] = []

        items = [
            f"{self.get_count(outcome)} {outcome.name}"
            for outcome in (
                Outcome.passed,
                Outcome.xfailed,
                Outcome.xpassed,
                Outcome.skipped,
                Outcome.failed,
                Outcome.error,
            )
            if self.get_count(outcome) > 0
        ]
        result.append("### 📊 Test Report\n")
        result.append(f"{len(self.tests)} tests - {', '.join(items)}")

        result.append("")

        if self.get_count(Outcome.failed) != 0:
            result.append("### ❌ Failures by owner\n")
            for owner, tests in self.failures.items():
                result.append(f"* {owner}: {len(tests)} failures")
                for test in tests:
                    result.append(f"    * {test.nodeid} ({test.weblog}/{test.scenario})")

            result.append("")

        return "\n".join(result)


def crawl_folder(base_dir: Path, summary: Summary) -> None:
    for entry in os.listdir(base_dir):
        entry_path = Path(base_dir) / entry

        if entry_path.is_file() and entry == REPORT_FILENAME:
            compute_file(entry_path, summary)

        elif entry_path.is_dir() and entry.startswith("logs"):
            crawl_folder(entry_path, summary)


def get_properties(node: ET.Element) -> dict[str, str]:
    result: dict[str, str] = {}
    for prop in node.iterfind("./properties/property"):
        result[prop.attrib["name"]] = prop.attrib["value"]

    return result


def compute_file(file_path: Path, summary: Summary) -> None:
    logging.info("Parse %s", file_path)

    with file_path.open("r") as f:
        root = ET.parse(f).getroot()  # noqa: S314

        for testsuite in root.iterfind("testsuite"):
            suite_properties = get_properties(testsuite)

            for testcase in testsuite.iterfind("testcase"):
                logging.debug("   Process %s", testcase.attrib["name"])

                test_properties = get_properties(testcase)
                test = Test(
                    nodeid=testcase.attrib["name"],
                    outcome=test_properties[PropertyName.OUTCOME],
                    scenario=suite_properties.get(PropertyName.SCENARIO, "unknown"),
                    weblog=suite_properties.get(PropertyName.WEBLOG, "unknown"),
                    owners=json.loads(test_properties.get(PropertyName.CODEOWNERS, "[]")),
                )
                summary.add_test(test)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a summary of test results.")
    parser.add_argument(
        "--base-dir",
        type=str,
        default=".",
        help=f"Base directory to start crawling for {REPORT_FILENAME} files.",
    )
    parser.add_argument(
        "--output-file",
        "-o",
        type=str,
        default="",
        help="Path to the output file for the summary. Default to stdout",
    )

    args = parser.parse_args()

    summary = Summary()

    crawl_folder(Path(args.base_dir), summary)

    result = summary.get_markdown()

    if args.output_file:
        with open(args.output_file, "w") as f:
            f.write(result)
    else:
        print(result)


if __name__ == "__main__":
    main()
