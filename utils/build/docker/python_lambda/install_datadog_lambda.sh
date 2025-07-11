#!/bin/bash

set -eu

cd /binaries

if [ "$(find . -maxdepth 1 -name "*.zip" | wc -l)" = "1" ]; then
    path=$(readlink -f "$(find . -maxdepth 1 -name "*.zip")")
    echo "Install datadog_lambda from ${path}"
    unzip "${path}" -d /opt
else
    echo "Fetching from latest GitHub release"
    curl -fsSLO https://github.com/DataDog/datadog-lambda-python/releases/latest/download/datadog_lambda_py-amd64-3.13.zip
    unzip -o datadog_lambda_py-amd64-3.13.zip -d /opt

    if [ ! -f datadog_lambda_py-amd64-3.13.zip ]; then
        echo "Failed to download datadog_lambda_py-amd64-3.13.zip"
        exit 1
    fi
fi
