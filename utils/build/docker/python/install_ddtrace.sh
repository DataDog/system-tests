#!/bin/bash

set -eu

cd /binaries

export CMAKE_BUILD_PARALLEL_LEVEL=$(nproc)
PYTHON_VERSION=$(python - <<'PY'
import sys
print(f"cp{sys.version_info.major}{sys.version_info.minor}")
PY
)

if [ "$(ls *.whl | wc -l)" = "1" ]; then
    path=$(readlink -f $(ls *.whl))
    echo "Install ddtrace from ${path}"
    pip install "ddtrace @ file://${path}"
elif [ $(ls python-load-from-pip | wc -l) = 1 ]; then
    echo "Install ddtrace from $(cat python-load-from-pip)"
    pip install "$(cat python-load-from-pip)"
elif [ $(ls *.whl | wc -l) = 0 ]; then
    echo "Install ddtrace from pypi"
    pip install ddtrace
elif [ "$(ls *$PYTHON_VERSION*.whl | wc -l)" = "1" ]; then
    path=$(readlink -f $(ls *$PYTHON_VERSION*.whl))
    echo "Install ddtrace from ${path} (selected automatically)"
    pip install "ddtrace @ file://${path}"
else
    echo "ERROR: Found several usable wheel files in binaries/, abort."
    exit 1
fi
