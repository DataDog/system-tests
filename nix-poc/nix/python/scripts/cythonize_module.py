"""Cythonize one module the way setup.py's cythonize() call does.

Usage: cythonize_module.py <dotted.module.name> <output dir>

The .pyx is found from the module name. Every directory holding a .pyx or .pxd gets an empty
__init__.py so cimports resolve; the real __init__.py files are not inputs, so editing them never
re-runs Cython.
"""

import os
import shutil
import sys

from Cython.Build import cythonize
from setuptools import Extension


def main(module: str, out: str) -> None:
    pyx = os.path.join(*module.split(".")) + ".pyx"
    for dirpath, _, filenames in os.walk("ddtrace"):
        if any(f.endswith((".pyx", ".pxd")) for f in filenames):
            parts = dirpath.split(os.sep)
            for i in range(1, len(parts) + 1):
                open(os.path.join(*parts[:i], "__init__.py"), "a").close()

    cythonize(
        [Extension(module, [pyx])],
        compile_time_env={
            "PY_MAJOR_VERSION": sys.version_info.major,
            "PY_MINOR_VERSION": sys.version_info.minor,
            "PY_MICRO_VERSION": sys.version_info.micro,
            "PY_VERSION_HEX": sys.hexversion,
        },
        compiler_directives={"language_level": "3"},
        force=True,
    )

    c_file = pyx[: -len(".pyx")] + ".c"
    os.makedirs(os.path.join(out, os.path.dirname(c_file)), exist_ok=True)
    shutil.copyfile(c_file, os.path.join(out, c_file))


if __name__ == "__main__":
    main(*sys.argv[1:])
