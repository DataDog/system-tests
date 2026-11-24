"""Copy the files setup.py's find_packages() and package_data put in the wheel.

Keep the excludes and patterns in sync with the setup() call in setup.py.
"""

import fnmatch
import os
import shutil
import sys

from setuptools import find_packages


EXCLUDE = [
    "tests*",
    "benchmarks*",
    "scripts*",
    "ddtrace.appsec._iast._taint_tracking._vendor.pybind11*",
    "ddtrace.internal.datadog.profiling.ddup.test*",
]

# Native libraries from package_data (libddwaf, libdd_wrapper) come from their own derivations.
PACKAGE_DATA = {
    "": ["*.pyi", "py.typed"],
    "ddtrace.appsec": ["rules.json"],
    "ddtrace.appsec.sca": ["_cve_data.json"],
    "ddtrace.internal": ["third-party.tar.gz"],
}


def main(src: str, out: str) -> None:
    for package in sorted(find_packages(where=src, exclude=EXCLUDE)):
        rel = os.path.join(*package.split("."))
        patterns = ["*.py"] + PACKAGE_DATA[""] + PACKAGE_DATA.get(package, [])
        for name in sorted(os.listdir(os.path.join(src, rel))):
            path = os.path.join(src, rel, name)
            if os.path.isfile(path) and any(fnmatch.fnmatch(name, p) for p in patterns):
                os.makedirs(os.path.join(out, rel), exist_ok=True)
                shutil.copyfile(path, os.path.join(out, rel, name))


if __name__ == "__main__":
    main(*sys.argv[1:])
