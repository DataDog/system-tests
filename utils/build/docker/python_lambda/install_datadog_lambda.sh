#!/bin/bash

set -eu

cd /binaries

if [ "$(find . -maxdepth 1 -name "*.zip" | wc -l)" = "1" ]; then
    path=$(readlink -f "$(find . -maxdepth 1 -name "*.zip")")
    echo "Install datadog_lambda from ${path}"
    unzip "${path}" -d /opt
else
    ARCH=$(uname -m | sed 's/x86_64/amd64/' | sed 's/aarch64/arm64/')
    ZIPFILE=datadog_lambda_py-"$ARCH"-3.13.zip
    if [ -f python-lambda-github-actions-artifact.json ]; then
        echo "Fetching from staged GitHub Actions artifact metadata..."
        ARCHIVE_URL=$(jq -r '.archive_download_url' python-lambda-github-actions-artifact.json)
        if [ -z "$ARCHIVE_URL" ] || [ "$ARCHIVE_URL" = "null" ]; then
            echo "Staged GitHub Actions artifact metadata is missing archive_download_url"
            exit 1
        fi
        GITHUB_AUTH_HEADER=()
        if [ -f /run/secrets/github_token ]; then
            GITHUB_AUTH_HEADER=(-H "Authorization: Bearer $(cat /run/secrets/github_token)")
        fi
        curl -fsSL "${GITHUB_AUTH_HEADER[@]}" -o /tmp/python-lambda-artifact.zip "$ARCHIVE_URL"
        mkdir -p /tmp/python-lambda-artifact
        unzip -o /tmp/python-lambda-artifact.zip -d /tmp/python-lambda-artifact
        cp "$(find /tmp/python-lambda-artifact -name "$ZIPFILE" | head -1)" .
    elif [ -f python-lambda-load-from-release ]; then
        RELEASE_TAG=$(cat python-lambda-load-from-release)
        curl -fsSLO "https://github.com/DataDog/datadog-lambda-python/releases/download/${RELEASE_TAG}/${ZIPFILE}"
    else
        echo "Fetching from latest GitHub release..."
        curl -fsSLO "https://github.com/DataDog/datadog-lambda-python/releases/latest/download/${ZIPFILE}"
    fi
    unzip -o datadog_lambda_py-"$ARCH"-3.13.zip -d /opt

    if [ ! -f "$ZIPFILE" ]; then
        echo "Failed to download ${ZIPFILE}"
        exit 1
    fi
fi
