"""Compute params files for the library_weblog_scenarios input of the GitLab end-to-end component (main.yml).

The input is a JSON object {library: {weblog: [entry, ...]}}, where each entry is either a scenario
name (uppercase, e.g. DEFAULT) or a scenario group name (lowercase, e.g. appsec).

compute-workflow-parameters.py is called once per (library, weblog), with only the scenarios/groups of
that weblog, and the results are merged into one params_<library>.json per library, which is what
build_pipeline.py expects.

    python3 utils/ci/gitlab/library_weblog_scenarios.py <json> --excluded-scenarios <names> --params-dir <dir>
        [-- <extra compute-workflow-parameters.py arguments>]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

COMPUTE_WORKFLOW_PARAMETERS = "utils/scripts/compute-workflow-parameters.py"


def get_compute_args(entries: list[str], excluded_scenarios: str) -> list[str]:
    """Return the --scenarios, --groups and --excluded-scenarios arguments for one weblog.

    Explicitly listed scenarios are removed from excluded_scenarios, so the exclusion only applies to
    scenarios coming from groups.
    """
    scenarios = sorted({entry for entry in entries if not entry.islower()})
    groups = sorted({entry for entry in entries if entry.islower()})
    excluded = [name.strip() for name in excluded_scenarios.split(",") if name.strip()]
    excluded = [name for name in excluded if name not in scenarios]
    return [
        "--scenarios",
        ",".join(scenarios),
        "--groups",
        ",".join(groups),
        "--excluded-scenarios",
        ",".join(excluded),
    ]


def merge_params(weblog_params: list[dict]) -> dict:
    """Merge params computed for each weblog of a library.

    Only the parts used by build_pipeline.py are merged: end-to-end jobs and weblogs are concatenated,
    and parametric (which is not weblog-bound) is enabled if it is enabled for any weblog. Other parts
    (miscs, SSI matrices...) are taken from the first weblog.
    """
    result = dict(weblog_params[0])
    parametric = next((p["parametric"] for p in weblog_params if p["parametric"]["enable"]), result["parametric"])
    parallel_jobs = [job for p in weblog_params for job in p["endtoend_defs"]["parallel_jobs"]]
    result["endtoend_defs"] = {
        "parallel_enable": len(parallel_jobs) > 0,
        "parallel_weblogs": [w for p in weblog_params for w in p["endtoend_defs"]["parallel_weblogs"]],
        "parallel_jobs": parallel_jobs,
    }
    result["parametric"] = parametric
    return result


def compute_params(
    library_weblog_scenarios: dict[str, dict[str, list[str]]],
    excluded_scenarios: str,
    params_dir: Path,
    extra_args: list[str],
) -> None:
    for library, weblog_scenarios in library_weblog_scenarios.items():
        weblog_params = []
        for weblog, entries in weblog_scenarios.items():
            output = params_dir / f"params_{library}__{weblog}.json"
            command = [
                sys.executable,
                COMPUTE_WORKFLOW_PARAMETERS,
                library,
                "--format",
                "json",
                "--weblogs",
                weblog,
                *get_compute_args(entries, excluded_scenarios),
                *extra_args,
                "--output",
                str(output),
            ]
            print(f"{library}/{weblog}: {' '.join(command[1:])}")  # noqa: T201
            subprocess.run(command, check=True)
            params = json.loads(output.read_text())

            if not params["endtoend_defs"]["parallel_jobs"] and not params["parametric"]["enable"]:
                print(  # noqa: T201
                    f"⚠️ {library}/{weblog}: no job to run, the weblog does not exist or "
                    f"does not support any of {', '.join(entries)}"
                )
            weblog_params.append(params)

        (params_dir / f"params_{library}.json").write_text(json.dumps(merge_params(weblog_params)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("library_weblog_scenarios", help="JSON object {library: {weblog: [scenario or group, ...]}}")
    parser.add_argument("--excluded-scenarios", default="", help="Comma-separated scenarios excluded from groups")
    parser.add_argument("--params-dir", required=True, help="Directory where params_<library>.json are written")
    parser.add_argument("extra_args", nargs="*", help="Extra arguments for compute-workflow-parameters.py")
    args = parser.parse_args(argv)

    compute_params(
        json.loads(args.library_weblog_scenarios), args.excluded_scenarios, Path(args.params_dir), args.extra_args
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
