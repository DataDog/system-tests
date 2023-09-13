#!/bin/bash

set -eu

if [ -z ${PYTHON_DDTRACE_PACKAGE} ]; then pip install ddtrace; else pip install $PYTHON_DDTRACE_PACKAGE; fi

python -c "import ddtrace; print(ddtrace.__version__)" > SYSTEM_TESTS_LIBRARY_VERSION

echo "dd-trace version is $(cat SYSTEM_TESTS_LIBRARY_VERSION)"
