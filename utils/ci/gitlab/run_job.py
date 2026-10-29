"""Run one of the job scripts of utils/ci/gitlab/jobs/: python utils/ci/gitlab/run_job.py <job>

Run as a file, this script has its own directory first in sys.path: the job scripts are imported as the
top-level `jobs` package, without loading the system-tests framework (utils/__init__.py). They only use the
standard library, so they work whatever the state of the rest of the clone, and without the venv.
"""

import importlib
import sys

JOBS = ("build_weblog", "run_scenario", "run_parametric", "push_to_test_optimization")


def main(argv: list[str]) -> None:
    if len(argv) != 1 or argv[0] not in JOBS:
        sys.exit(f"usage: run_job.py {{{','.join(JOBS)}}}")
    importlib.import_module(f"jobs.{argv[0]}").main()


if __name__ == "__main__":
    main(sys.argv[1:])
