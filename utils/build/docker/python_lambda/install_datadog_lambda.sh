#!/bin/bash

set -eu

cd /binaries

if [ "$(find . -maxdepth 1 -name "*.zip" | wc -l)" = "1" ]; then
    path=$(readlink -f "$(find . -maxdepth 1 -name "*.zip")")
    echo "Install datadog_lambda from ${path}"
    unzip "${path}" -d /opt
else
    echo "Fetching from latest GitHub release..."
    ARCH=$(uname -m | sed 's/x86_64/amd64/' | sed 's/aarch64/arm64/')
    echo https://github.com/DataDog/datadog-lambda-python/releases/latest/download/datadog_lambda_py-"$ARCH"-3.13.zip
    curl -fsSLO --retry 3 --retry-delay 5 --retry-connrefused --retry-all-errors https://github.com/DataDog/datadog-lambda-python/releases/latest/download/datadog_lambda_py-"$ARCH"-3.13.zip
    unzip -o datadog_lambda_py-"$ARCH"-3.13.zip -d /opt

    if [ ! -f datadog_lambda_py-"$ARCH"-3.13.zip ]; then
        echo "Failed to download datadog_lambda_py-""$ARCH""-3.13.zip"
        exit 1
    fi
fi

# a custom Datadog Lambda extension build (bottlecap binary, and its datadog_wrapper) replaces the one of the base image
if [ -f datadog-agent ]; then
    echo "Install the Datadog Lambda extension from binaries/datadog-agent"
    install -m 0755 datadog-agent /opt/extensions/datadog-agent
fi
if [ -f datadog_wrapper ]; then
    echo "Install the Datadog Lambda wrapper from binaries/datadog_wrapper"
    install -m 0755 datadog_wrapper /opt/datadog_wrapper
fi

# read by build.sh, to label the image with it, like the healthcheck reports it (datadog_lambda.__version__), with
# the layer on the path, as the lambda runtime does
PYTHONPATH="$(echo /opt/python/lib/python*/site-packages):/opt/python" \
    python -c "import datadog_lambda; open('/binaries/SYSTEM_TESTS_LIBRARY_VERSION', 'w').write(datadog_lambda.__version__)"
