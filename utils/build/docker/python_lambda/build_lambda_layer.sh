#!/usr/bin/env bash

set -euo pipefail

ARCH=${ARCH:-$(uname -m)}
PYTHON_VERSION=${PYTHON_VERSION:-3.13}
PYTHON_VERSION_NO_DOT=$(echo "$PYTHON_VERSION" | tr -d '.')

if [ "$ARCH" = "x86_64" ]; then
    ARCH="amd64"
fi
if [ "$ARCH" = "aarch64" ]; then
    ARCH="arm64"
fi

cd binaries

SKIP_BUILD=0

if [ -e "datadog-lambda-python" ]; then
    echo "datadog-lambda-python already exists, skipping clone."
elif [ "$(find . -maxdepth 1 -name "*.zip" | wc -l)" = "1" ]; then
    echo "Using provided datadog-lambda-python layer."
    SKIP_BUILD=1
elif command -v aws >/dev/null 2>&1 && aws sts get-caller-identity >/dev/null 2>&1; then
    echo "AWS credentials detected. Downloading datadog-lambda-python layer from AWS..."
    REGION=${AWS_DEFAULT_REGION:-us-east-1}
    ARCH_SUFFIX=$(if [ "$ARCH" = "arm64" ]; then echo "-ARM"; else echo ""; fi)
    LAMBDA_LAYER_NAME="arn:aws:lambda:$REGION:464622532012:layer:Datadog-Python$PYTHON_VERSION_NO_DOT$ARCH_SUFFIX"

    # The layer version cannot be retrieve directly from AWS but is present as the minor version in the datadog_lambda package
    # in the PyPI index.
    LAYER_VERSION=$(head -n 1 <(pip index versions datadog_lambda) | cut -d '.' -f2)

    if [ "$LAYER_VERSION" != "None" ] && [ -n "$LAYER_VERSION" ]; then
        echo "Downloading layer version $LAYER_VERSION for $LAMBDA_LAYER_NAME from region $REGION"

        # Get the download URL
        DOWNLOAD_URL=$(aws lambda get-layer-version \
            --layer-name "$LAMBDA_LAYER_NAME" \
            --version-number "$LAYER_VERSION" \
            --query 'Content.Location' \
            --output text \
            --region "$REGION")

        if [ -n "$DOWNLOAD_URL" ] && [ "$DOWNLOAD_URL" != "None" ]; then
            # Download the layer
            curl -L "$DOWNLOAD_URL" -o "datadog_lambda_py-${ARCH}-${PYTHON_VERSION}.zip"
            echo "Successfully downloaded datadog-lambda-python layer from AWS"
            SKIP_BUILD=1
        else
            echo "Failed to get download URL for layer. Falling back to git clone..."
            exit 1
        fi
    else
        echo "No layer version found. Falling back to git clone..."
        exit 1
    fi
else
    echo "Impossible to download datadog-lambda-python layer from AWS and no local layer provided, Aborting."
    exit 1
fi

if [[ $SKIP_BUILD -eq 0 ]]; then
    if [ -e "datdog-lambda-python/dd-trace-py" ]; then
        echo "Install from local folder /binaries/datadog-lambda-python/dd-trace-py"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' 's|^ddtrace =.*$|ddtrace = { path = "./dd-trace-py" }|' datadog-lambda-python/pyproject.toml
        else
            sed -i 's|^ddtrace =.*$|ddtrace = { path = "./dd-trace-py" }|' datadog-lambda-python/pyproject.toml
        fi
    elif [ "$(find . -maxdepth 1 -name "datadog-lambda-python/*.whl" | wc -l)" = "1" ]; then
        path=$(readlink -f "$(find . -maxdepth 1 -name "*.whl")")
        echo "Install ddtrace from ${path}"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|^ddtrace =.*$|ddtrace = { path = \"file://${path}\" }|" datadog-lambda-python/pyproject.toml
        else
            sed -i "s|^ddtrace =.*$|ddtrace = { path = \"file://${path}\" }|" datadog-lambda-python/pyproject.toml
        fi
    elif [ "$(find . -maxdepth 1 -name "*.whl" | wc -l)" = "0" ]; then
        echo "Install ddtrace from pypi"
        # Keep the default ddtrace dependency in pyproject.toml
    else
        echo "ERROR: Found several wheel files in binaries/, abort."
        exit 1
    fi

    # Build the datadog-lambda-python package
    cd datadog-lambda-python
    ARCH=$ARCH PYTHON_VERSION=$PYTHON_VERSION bash ./scripts/build_layers.sh

    mv .layers/*.zip ../
    cd ..
fi

cd ..
