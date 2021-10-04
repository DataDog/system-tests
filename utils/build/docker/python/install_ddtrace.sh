#!/bin/bash

set -eu

cd binaries

if [ "$(ls *.whl *.tar.gz | wc -l)" = "1" ]; then
    path=$(readlink -f $(ls *.whl *.tar.gz))
    echo "Install ddtrace from ${path}"
    pip install "ddtrace[appsec-beta] @ file://${path}"
elif [ $(ls python-load-from-pip | wc -l) = 1 ]; then
    echo "Install ddtrace from $(cat python-load-from-pip)"
    pip install "$(cat python-load-from-pip)"
elif [ $(ls *.whl | wc -l) = 0 ]; then
    echo "Install ddtrace from pypi"
    pip install ddtrace
else
    echo "ERROR: Found several wheel files in binaries/, abort."
    exit 1
fi

cd -

python -c "import ddtrace; print(ddtrace.__version__)" > SYSTEM_TESTS_LIBRARY_VERSION
