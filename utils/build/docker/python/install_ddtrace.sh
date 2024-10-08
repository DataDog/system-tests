#!/bin/bash

set -eu

cd /binaries

if [ -e "dd-trace-py" ]; then
    echo "Install from local folder /binaries/dd-trace-py"
    pip install /binaries/dd-trace-py
elif [ "$(ls *.whl *.tar.gz | grep -v 'datadog-dotnet-apm.tar.gz' | grep -v 'dd-library-php-x86_64-linux-gnu.tar.gz' | wc -l)" = "1" ]; then
    path=$(readlink -f $(ls *.whl *.tar.gz | grep -v 'datadog-dotnet-apm.tar.gz' | grep -v 'dd-library-php-x86_64-linux-gnu.tar.gz'))
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

# python uses the next API to get the library version. See https://github.com/DataDog/system-tests/issues/2799
echo "0.0.0" > SYSTEM_TESTS_LIBRARY_VERSION
echo "0.0.0" > SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION