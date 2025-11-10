#!/bin/bash

set -eu

cd /binaries

export CMAKE_BUILD_PARALLEL_LEVEL=$(nproc)
PYTHON_VERSION=$(python --version | sed -E 's/Python ([0-9]+)\.([0-9]+)\.[0-9]+/cp\1\2/')

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
    echo "In the system-tests CI see (python,dev)/Get parameters/Get dev artifacts for exact ref"
    pip install "ddtrace @ file://${path}"
else
    echo "ERROR: Found several usable wheel files in binaries/, abort."
    exit 1
fi
