#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


REPO_ROOT = _repo_root()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from utils._context._scenarios import get_all_scenarios  # noqa: E402
from utils.const import COMPONENT_GROUPS  # noqa: E402
from utils.manifest import Manifest, TestDeclaration  # noqa: E402


RESULTS_PATH = Path("logs_isolated_matrix/results.jsonl")
SCENARIO_MAP_PATH = Path("logs_mock_the_test/scenarios.json")


@dataclass(frozen=True)
class ExecutionKey:
    library: str
    weblog_variant: str
    scenario: str
    test_case: str


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run isolated system-tests matrix. "
            "For each library+weblog: build once, then run each scenario/test-case individually."
        )
    )
    parser.add_argument(
        "--library",
        action="append",
        dest="libraries",
        default=[],
        help="Repeatable. Library to include. If omitted, all buildable libraries are used.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        dest="scenarios",
        default=[],
        help="Repeatable. Scenario to include. If omitted, all scenarios are used (TEST_THE_TEST excluded).",
    )
    parser.add_argument(
        "--weblog-variant",
        action="append",
        dest="weblog_variants",
        default=[],
        help=("Repeatable. Restrict weblog variants. If omitted, all weblog variants for selected libraries are used."),
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip test-case executions already present in logs_isolated_matrix/results.jsonl.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without building/running tests.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first build/discovery/test failure.",
    )
    parser.add_argument(
        "--refresh-scenario-map",
        action="store_true",
        help="Force regeneration of the scenario->nodeids map even if it already exists.",
    )
    return parser.parse_args()


def _all_libraries() -> list[str]:
    return sorted(COMPONENT_GROUPS.buildable)


def _all_scenarios() -> list[str]:
    return sorted(s.name for s in get_all_scenarios())


def _default_scenarios() -> list[str]:
    return [name for name in _all_scenarios() if name != "TEST_THE_TEST"]


def _weblogs_for_library(root: Path, library: str) -> list[str]:
    weblog_dir = root / "utils" / "build" / "docker" / library
    if not weblog_dir.is_dir():
        return []

    result: list[str] = []
    for dockerfile in weblog_dir.glob("*.Dockerfile"):
        if ".base." in dockerfile.name:
            continue
        result.append(dockerfile.stem)
    return sorted(result)


def _ensure_output_path(root: Path) -> Path:
    output = root / RESULTS_PATH
    output.parent.mkdir(parents=True, exist_ok=True)
    return output


def _load_resume_keys(path: Path) -> set[ExecutionKey]:
    if not path.exists():
        return set()

    keys: set[ExecutionKey] = set()
    with path.open(encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue

            if row.get("stage") != "run":
                continue

            if row.get("test_case") is None:
                continue

            keys.add(
                ExecutionKey(
                    library=str(row.get("library", "")),
                    weblog_variant=str(row.get("weblog_variant", "")),
                    scenario=str(row.get("scenario", "")),
                    test_case=str(row.get("test_case", "")),
                )
            )
    return keys


def _append_result(path: Path, payload: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, sort_keys=True) + "\n")


def _run_command(command: list[str], *, cwd: Path, env: dict[str, str], dry_run: bool) -> subprocess.CompletedProcess:
    rendered = " ".join(command)
    print(f"$ {rendered}")
    if dry_run:
        return subprocess.CompletedProcess(command, 0, "", "")

    return subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _build_scenario_map(root: Path, *, refresh: bool, dry_run: bool) -> dict[str, list[str]]:
    """Returns a mapping `nodeid -> [scenario_name, ...]` covering every test in the repo.

    Generated once via `./run.sh MOCK_THE_TEST --collect-only --scenario-report`,
    which produces `logs_mock_the_test/scenarios.json`. The file is independent of
    library and weblog variant.
    """

    scenario_map_file = root / SCENARIO_MAP_PATH

    must_generate = refresh or not scenario_map_file.exists()

    if must_generate:
        if dry_run and not refresh:
            print(f"$ ./run.sh MOCK_THE_TEST --collect-only --scenario-report  # would generate {SCENARIO_MAP_PATH}")
            return {}

        env = os.environ.copy()
        completed = _run_command(
            ["./run.sh", "MOCK_THE_TEST", "--collect-only", "--scenario-report"],
            cwd=root,
            env=env,
            dry_run=False,
        )
        if completed.returncode != 0:
            print(completed.stdout)
            print(completed.stderr, file=sys.stderr)
            raise RuntimeError("failed to generate scenario map via MOCK_THE_TEST collect-only")

    with scenario_map_file.open(encoding="utf-8") as f:
        return json.load(f)


def _invert_scenario_map(scenario_map: dict[str, list[str]]) -> dict[str, list[str]]:
    """`nodeid -> [scenarios]` => `scenario -> [nodeids]` (sorted, de-duplicated)."""

    inverted: dict[str, set[str]] = {}
    for nodeid, scenario_names in scenario_map.items():
        for scenario in scenario_names:
            inverted.setdefault(scenario, set()).add(nodeid)
    return {scenario: sorted(nodeids) for scenario, nodeids in inverted.items()}


def _filter_relevant_nodeids(
    *,
    nodeids: list[str],
    manifest: Manifest,
) -> list[str]:
    """Removes nodeids whose manifest declarations include `irrelevant` for the
    current `(library, weblog_variant)`.
    """
    result = []
    for nodeid in nodeids:
        declarations = manifest.get_declarations(nodeid)
        if any(d.value == TestDeclaration.IRRELEVANT for d in declarations):
            continue
        result.append(nodeid)
    return result


def _select_values(requested: list[str], available: list[str], what: str) -> list[str]:
    if not requested:
        return available

    requested_set = set(requested)
    available_set = set(available)
    missing = sorted(requested_set - available_set)
    if missing:
        print(f"error: unknown {what}: {', '.join(missing)}", file=sys.stderr)
        sys.exit(2)

    return sorted(requested_set)


def main() -> int:
    args = _parse_args()
    root = _repo_root()

    all_libraries = _all_libraries()
    libraries = _select_values(args.libraries, all_libraries, "library")

    all_scenarios = _all_scenarios()
    scenarios = _select_values(args.scenarios, all_scenarios, "scenario") if args.scenarios else _default_scenarios()

    weblog_filters = set(args.weblog_variants)

    results_path = _ensure_output_path(root)
    done_keys = _load_resume_keys(results_path) if args.resume else set()

    print(f"Libraries: {', '.join(libraries)}")
    print(f"Scenarios: {', '.join(scenarios)}")
    if weblog_filters:
        print(f"Weblog filter: {', '.join(sorted(weblog_filters))}")
    print(f"Results: {results_path}")

    # Discovery phase: one global pass independent of library/weblog
    print("\n=== global scenario discovery ===")
    discovery_start = time.time()
    raw_scenario_map = _build_scenario_map(root, refresh=args.refresh_scenario_map, dry_run=args.dry_run)
    scenario_to_nodeids = _invert_scenario_map(raw_scenario_map)
    discovery_duration = round(time.time() - discovery_start, 3)

    _append_result(
        results_path,
        {
            "stage": "discover_global",
            "timestamp": int(time.time()),
            "duration_seconds": discovery_duration,
            "scenarios_seen": sorted(scenario_to_nodeids.keys()),
            "test_count_total": sum(len(v) for v in scenario_to_nodeids.values()),
        },
    )

    if args.dry_run and not raw_scenario_map:
        # Nothing else useful we can do without a real scenario map
        print("(dry-run) no scenario map available; skipping per-(library,weblog) phase")
        return 0

    for library in libraries:
        weblogs = _weblogs_for_library(root, library)
        if weblog_filters:
            weblogs = [w for w in weblogs if w in weblog_filters]

        if not weblogs:
            print(f"warn: no weblog variants selected for library={library}")
            continue

        for weblog_variant in weblogs:
            print(f"\n=== library={library} weblog_variant={weblog_variant} ===")

            # Use a permissive components dict so that version-bound declarations
            # don't accidentally filter out tests. We only care about `irrelevant`,
            # which depends on weblog variant, not on component versions.
            try:
                manifest = Manifest(components={}, weblog=weblog_variant)
            except Exception as exc:
                print(f"warn: failed to load manifest for {library}/{weblog_variant}: {exc}", file=sys.stderr)
                manifest = None  # type: ignore[assignment]

            build_start = time.time()
            build_env = os.environ.copy()
            build_result = _run_command(
                ["./build.sh", "--library", library, "--weblog-variant", weblog_variant],
                cwd=root,
                env=build_env,
                dry_run=args.dry_run,
            )
            build_duration = round(time.time() - build_start, 3)

            _append_result(
                results_path,
                {
                    "stage": "build",
                    "timestamp": int(time.time()),
                    "library": library,
                    "weblog_variant": weblog_variant,
                    "command": ["./build.sh", "--library", library, "--weblog-variant", weblog_variant],
                    "exit_code": build_result.returncode,
                    "success": build_result.returncode == 0,
                    "duration_seconds": build_duration,
                },
            )

            if build_result.returncode != 0:
                print(build_result.stdout)
                print(build_result.stderr, file=sys.stderr)
                if args.fail_fast:
                    return 1
                continue

            for scenario in scenarios:
                nodeids = scenario_to_nodeids.get(scenario, [])

                if manifest is not None and nodeids:
                    relevant = _filter_relevant_nodeids(nodeids=nodeids, manifest=manifest)
                else:
                    relevant = list(nodeids)

                _append_result(
                    results_path,
                    {
                        "stage": "discover",
                        "timestamp": int(time.time()),
                        "library": library,
                        "weblog_variant": weblog_variant,
                        "scenario": scenario,
                        "test_count_total": len(nodeids),
                        "test_count_relevant": len(relevant),
                    },
                )

                for test_case in relevant:
                    key = ExecutionKey(
                        library=library,
                        weblog_variant=weblog_variant,
                        scenario=scenario,
                        test_case=test_case,
                    )

                    if key in done_keys:
                        continue

                    env = os.environ.copy()
                    env["TEST_LIBRARY"] = library
                    env["WEBLOG_VARIANT"] = weblog_variant

                    run_start = time.time()
                    run_result = _run_command(
                        ["./run.sh", scenario, test_case],
                        cwd=root,
                        env=env,
                        dry_run=args.dry_run,
                    )
                    run_duration = round(time.time() - run_start, 3)
                    success = run_result.returncode == 0

                    _append_result(
                        results_path,
                        {
                            "stage": "run",
                            "timestamp": int(time.time()),
                            "library": library,
                            "weblog_variant": weblog_variant,
                            "scenario": scenario,
                            "test_case": test_case,
                            "exit_code": run_result.returncode,
                            "success": success,
                            "status": "success" if success else "failure",
                            "duration_seconds": run_duration,
                        },
                    )

                    if args.resume:
                        done_keys.add(key)

                    if run_result.returncode != 0 and args.fail_fast:
                        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
