"""Compile one setuptools Extension described by the JSON in $extensionSpec.

Usage: build_extension.py <output dir>

The module lands at <output dir>/<package path>/<name><EXT_SUFFIX>, as in a wheel.
"""

import json
import os
import sys

from setuptools import Extension
from setuptools import setup


def main(out: str) -> None:
    spec = json.loads(os.environ["extensionSpec"])
    extension = Extension(
        spec["module"],
        sources=spec["sources"],
        extra_compile_args=spec["extraCompileArgs"],
        define_macros=[tuple(m) for m in spec["defineMacros"]],
        include_dirs=spec["includeDirs"],
        libraries=spec["libraries"],
    )
    setup(
        name="ddtrace-extension",
        ext_modules=[extension],
        script_args=[
            "build_ext",
            "--build-lib",
            out,
            "--build-temp",
            os.path.join(os.environ["NIX_BUILD_TOP"], "build-temp"),
        ],
    )


if __name__ == "__main__":
    main(*sys.argv[1:])
