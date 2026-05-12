#!/bin/bash

set -eu

cd /binaries

if [ "$(find . -maxdepth 1 -name "*.zip" | wc -l)" = "1" ]; then
    path=$(readlink -f "$(find . -maxdepth 1 -name "*.zip")")
    echo "Install datadog_lambda from ${path}"
    unzip "${path}" -d /opt
else
    echo "Fetching from latest GitHub release..."
    NODE_MAJOR=$(node -e "console.log(process.version.split('.')[0].slice(1))")
    # Map major version to the runtime version used by datadog-lambda-js release assets.
    # See https://github.com/DataDog/datadog-lambda-js/blob/main/.gitlab/datasources/runtimes.yaml
    case "${NODE_MAJOR}" in
        18) NODE_VERSION="18.12" ;;
        20) NODE_VERSION="20.19" ;;
        22) NODE_VERSION="22.11" ;;
        24) NODE_VERSION="24.11" ;;
        *)  echo "Unsupported Node.js major version: ${NODE_MAJOR}"; exit 1 ;;
    esac
    echo "Detected Node.js major: ${NODE_MAJOR}, using layer runtime version: ${NODE_VERSION}"

    LATEST_TAG=$(curl -fsSL -H "Accept: application/vnd.github.v3+json" \
        https://api.github.com/repos/DataDog/datadog-lambda-js/releases/latest \
        | grep '"tag_name"' | head -1 | sed 's/.*"tag_name": *"//;s/".*//')
    echo "Latest release tag: ${LATEST_TAG}"

    ZIP_NAME="datadog_lambda_node${NODE_VERSION}.zip"
    DOWNLOAD_URL="https://github.com/DataDog/datadog-lambda-js/releases/download/${LATEST_TAG}/${ZIP_NAME}"
    echo "Downloading ${DOWNLOAD_URL}"
    curl -fsSLO "${DOWNLOAD_URL}"

    if [ ! -f "${ZIP_NAME}" ]; then
        echo "Failed to download ${ZIP_NAME}"
        exit 1
    fi

    unzip -o "${ZIP_NAME}" -d /opt
fi
