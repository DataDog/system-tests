#!/bin/bash

set -eu

cd /binaries

if [ -e "dd-trace-py" ]; then
    echo "Install from local folder /binaries/dd-trace-py"
    pip install /binaries/dd-trace-py
elif [ "$(ls *.whl | wc -l)" = "1" ]; then
    path=$(readlink -f $(ls *.whl))
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
python /binaries/get_appsec_rules_version.py > SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
touch SYSTEM_TESTS_LIBDDWAF_VERSION

echo "dd-trace version is $(cat SYSTEM_TESTS_LIBRARY_VERSION)"
echo "appsec rules version is $(cat SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION)"
