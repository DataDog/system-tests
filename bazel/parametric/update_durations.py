from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from statistics import median
from typing import Any, Literal


_LIFECYCLE_PHASES = ("setup", "call", "teardown")
Target = Literal["go", "python"]


def lifecycle_duration(test: dict[str, Any]) -> float:
    total = 0.0
    for phase in _LIFECYCLE_PHASES:
        phase_report = test.get(phase, {})
        if not isinstance(phase_report, dict):
            raise TypeError(f"Invalid {phase!r} report for {test.get('nodeid')!r}")
        duration = phase_report.get("duration", 0.0)
        if not isinstance(duration, (int, float)) or isinstance(duration, bool):
            raise TypeError(f"Non-numeric {phase!r} duration for {test.get('nodeid')!r}: {duration!r}")
        if duration < 0:
            raise ValueError(f"Invalid {phase!r} duration for {test.get('nodeid')!r}: {duration!r}")
        total += float(duration)
    return total


def aggregate_reports(report_paths: list[Path], *, precision: int = 6) -> dict[str, float]:
    samples: dict[str, list[float]] = defaultdict(list)
    for report_path in sorted(report_paths):
        report = json.loads(report_path.read_text(encoding="utf-8"))
        tests = report.get("tests")
        if not isinstance(tests, list):
            raise TypeError(f"Report has no test list: {report_path}")
        for test in tests:
            if not isinstance(test, dict):
                raise TypeError(f"Report contains an invalid test entry: {report_path}")
            node_id = test.get("nodeid")
            if not isinstance(node_id, str):
                raise TypeError(f"Report contains a non-string node ID: {report_path}")
            if not node_id:
                raise ValueError(f"Report contains an invalid node ID: {report_path}")
            samples[node_id].append(lifecycle_duration(test))

    if not samples:
        raise ValueError("No test durations found in the supplied Bazel reports")

    return {node_id: round(median(samples[node_id]), precision) for node_id in sorted(samples)}


def find_reports(testlogs: Path, *, target: Target | None = None) -> list[Path]:
    if not testlogs.is_dir():
        raise FileNotFoundError(f"Bazel testlogs directory does not exist: {testlogs}")
    target_root = testlogs / "bazel" / "parametric"
    available_targets = [name for name in ("go", "python") if (target_root / name).is_dir()]
    if target is None and len(available_targets) > 1:
        raise ValueError("--target is required when the testlogs tree contains both go and python results")
    selected_target = target or (available_targets[0] if available_targets else None)
    if selected_target is not None and available_targets and selected_target not in available_targets:
        raise ValueError(f"No {selected_target!r} reports found below {testlogs}")
    search_root = target_root / selected_target if selected_target is not None and available_targets else testlogs
    reports = sorted(search_root.rglob("report.json"))
    if not reports:
        raise ValueError(f"No report.json files found below {testlogs}")
    return reports


def write_manifest(durations: dict[str, float], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(durations, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a pytest-split duration manifest from Bazel JSON reports")
    parser.add_argument("--testlogs", type=Path, required=True, help="Bazel testlogs tree containing report.json files")
    parser.add_argument("--output", type=Path, required=True, help="Destination pytest-split duration JSON")
    parser.add_argument("--target", choices=("go", "python"), help="Parametric Bazel target to read")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_manifest(aggregate_reports(find_reports(args.testlogs, target=args.target)), args.output)


if __name__ == "__main__":
    main()
