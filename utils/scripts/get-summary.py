import argparse
from collections import defaultdict
from enum import StrEnum
import json
import os
from pathlib import Path


class Outcome(StrEnum):
    passed = "passed"
    failed = "failed"
    skipped = "skipped"
    error = "error"
    xfailed = "xfailed"
    xpassed = "xpassed"


class Test:
    def __init__(self, context: dict, nodeid: str, outcome: str, metadata: dict, **kwargs: dict):
        self.nodeid = nodeid
        self.outcome = Outcome(outcome)
        self.metadata = metadata
        self.extra = kwargs
        self.context = context

    @property
    def scenario(self) -> str:
        return self.context.get("scenario", "unknown")

    @property
    def weblog(self) -> str:
        return self.context.get("weblog_variant", "unknown")


class Summary:
    def __init__(self):
        self.tests: list[Test] = []
        self.tests_by_outcome: dict[Outcome, list[Test]] = defaultdict(list)
        self.failures: dict[str, list[Test]] = {}

    def add_test(self, test: Test) -> None:
        self.tests.append(test)
        self.tests_by_outcome[test.outcome].append(test)

        if test.outcome == Outcome.failed:
            for owner in test.metadata.get("owners", []):
                if owner not in self.failures:
                    self.failures[owner] = []
                self.failures[owner].append(test)

    def get_count(self, outcome: Outcome) -> int:
        return len(self.tests_by_outcome[outcome])

    def get_markdown(self) -> str:
        result: list[str] = []

        items = [
            f"{self.get_count(outcome)} {outcome.name}"
            for outcome in (Outcome.passed, Outcome.xpassed, Outcome.skipped, Outcome.failed)
            if self.get_count(outcome) > 0
        ]
        result.append("== 📊 Test Report ==\n")
        result.append(f"{len(self.tests)} tests - {', '.join(items)}")

        result.append("")

        if self.get_count(Outcome.failed) != 0:
            result.append("== ❌ Failures by owner ==\n")
            for owner, tests in self.failures.items():
                result.append(f"* {owner}: {len(tests)} failures")
                for test in tests:
                    result.append(f"    * {test.nodeid} ({test.weblog}/{test.scenario})")

            result.append("")

        return "\n".join(result)


def crawl_folder(base_dir: Path, summary: Summary) -> None:
    for entry in os.listdir(base_dir):
        entry_path = Path(base_dir) / entry

        if entry_path.is_file() and entry == "report.json":
            compute_file(entry_path, summary)

        elif entry_path.is_dir() and entry.startswith("logs"):
            crawl_folder(entry_path, summary)


def compute_file(file_path: Path, summary: Summary) -> None:
    with file_path.open("r") as f:
        data = json.load(f)

        for test_kwargs in data["tests"]:
            test = Test(context=data["context"], **test_kwargs)
            summary.add_test(test)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a summary of test results.")
    parser.add_argument(
        "--base-dir",
        type=str,
        default=".",
        help="Base directory to start crawling for report.json files.",
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
