#!/bin/bash

set -eu

cd /binaries

if [ "$(find . -maxdepth 1 -name "*.zip" | wc -l)" = "1" ]; then
    path=$(readlink -f "$(find . -maxdepth 1 -name "*.zip")")
    echo "Install datadog_lambda from ${path}"
    unzip "${path}" -d /opt
else
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

    ZIP_NAME="datadog_lambda_node${NODE_VERSION}.zip"
    if [ -f nodejs-lambda-github-actions-artifact.json ]; then
        echo "Fetching from staged GitHub Actions artifact metadata..."
        ARCHIVE_URL=$(jq -r '.archive_download_url' nodejs-lambda-github-actions-artifact.json)
        if [ -z "$ARCHIVE_URL" ] || [ "$ARCHIVE_URL" = "null" ]; then
            echo "Staged GitHub Actions artifact metadata is missing archive_download_url"
            exit 1
        fi
        GITHUB_AUTH_HEADER=()
        if [ -f /run/secrets/github_token ]; then
            GITHUB_AUTH_HEADER=(-H "Authorization: Bearer $(cat /run/secrets/github_token)")
        fi
        curl -fsSL "${GITHUB_AUTH_HEADER[@]}" -o /tmp/nodejs-lambda-artifact.zip "$ARCHIVE_URL"
        mkdir -p /tmp/nodejs-lambda-artifact
        unzip -o /tmp/nodejs-lambda-artifact.zip -d /tmp/nodejs-lambda-artifact
        cp "$(find /tmp/nodejs-lambda-artifact -name "$ZIP_NAME" | head -1)" .
    else
        if [ -f nodejs-lambda-load-from-release ]; then
            LATEST_TAG=$(cat nodejs-lambda-load-from-release)
        else
            LATEST_TAG=$(curl -fsSL -H "Accept: application/vnd.github.v3+json" \
                https://api.github.com/repos/DataDog/datadog-lambda-js/releases/latest \
                | grep '"tag_name"' | head -1 | sed 's/.*"tag_name": *"//;s/".*//')
        fi
        echo "Release tag: ${LATEST_TAG}"
        DOWNLOAD_URL="https://github.com/DataDog/datadog-lambda-js/releases/download/${LATEST_TAG}/${ZIP_NAME}"
        echo "Downloading ${DOWNLOAD_URL}"
        curl -fsSLO "${DOWNLOAD_URL}"
    fi

    if [ ! -f "${ZIP_NAME}" ]; then
        echo "Failed to download ${ZIP_NAME}"
        exit 1
    fi

    unzip -o "${ZIP_NAME}" -d /opt
fi
