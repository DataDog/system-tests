#!/bin/bash

set -eu

cd /binaries

export CMAKE_BUILD_PARALLEL_LEVEL=$(nproc)
PYTHON_VERSION=$(python --version | sed -E 's/Python ([0-9]+)\.([0-9]+)\.[0-9]+/cp\1\2/')

if [ $(ls python-load-from-local | wc -l) = 1 ]; then
    echo "Using local dd-trace-py set in PYTHONPATH"
    echo "Installing remaining dependencies from the official ddtrace package"
    pip install ddtrace
elif [ "$(ls *.whl | wc -l)" = "1" ]; then
    path=$(readlink -f $(ls *.whl))
    echo "Install ddtrace from ${path}"
    pip install "ddtrace @ file://${path}"
elif [ $(ls python-load-from-s3 | wc -l) = 1 ]; then
    GIT_REF=$(cat python-load-from-s3)
    echo "Install ddtrace from S3, git ref: ${GIT_REF}"
    # Install from S3 bucket
    # NOTE: Artifacts age out after 2 weeks, if this fails then you need to first run the dd-trace-py GitLab CI for the desired commit again
    # NOTE: Must have `--no-index` otherwise `pip` will look for the highest available version between S3 and PyPI
    pip download --no-index --no-deps --find-links https://dd-trace-py-builds.s3.amazonaws.com/${GIT_REF}/index.html --pre ddtrace
    pip install ./*.whl
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
