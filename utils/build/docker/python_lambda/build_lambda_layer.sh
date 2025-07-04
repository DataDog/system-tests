#!/usr/bin/env bash

set -euo pipefail

ARCH=${ARCH:-$(uname -m)}
PYTHON_VERSION=${PYTHON_VERSION:-3.13}
PYTHON_VERSION_NO_DOT=$(echo "$PYTHON_VERSION" | cut -d'.' -f1-2)

if [ "$ARCH" = "x86_64" ]; then
    ARCH="amd64"
fi
if [ "$ARCH" = "aarch64" ]; then
    ARCH="arm64"
fi

cd binaries

SKIP_BUILD=0

# Reexport all SYSTEM_TESTS_AWS_* variables as AWS_* variables
for var in $(compgen -v SYSTEM_TESTS_AWS_); do
    export "${var/SYSTEM_TESTS_AWS_/AWS_}"
done
echo "Following AWS variables are set:"
env | grep '^AWS_'

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

    # Get the latest layer version
    LAYER_VERSION=$(aws lambda list-layer-versions \
        --layer-name "$LAMBDA_LAYER_NAME" \
        --query 'LayerVersions[0].Version' \
        --output text \
        --region "$REGION")

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
        fi
    else
        echo "No layer version found. Falling back to git clone..."
    fi
else
    echo "Impossible to download datadog-lambda-python layer from AWS and no local layer provided, Aborting."
    exit 1
fi

# Patch the ddtrace dependency in datadog-lambda-python based on the same rules as install_ddtrace.sh
if [[ $SKIP_BUILD -eq 0 ]]; then
    if [ -e "dd-trace-py" ]; then
        echo "Install from local folder /binaries/dd-trace-py"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' 's|^ddtrace =.*$|ddtrace = { path = "./dd-trace-py" }|' datadog-lambda-python/pyproject.toml
        else
            sed -i 's|^ddtrace =.*$|ddtrace = { path = "./dd-trace-py" }|' datadog-lambda-python/pyproject.toml
        fi
        cp -r dd-trace-py datadog-lambda-python/dd-trace-py
    elif [ "$(find . -maxdepth 1 -name "*.whl" | wc -l)" = "1" ]; then
        path=$(readlink -f "$(find . -maxdepth 1 -name "*.whl")")
        echo "Install ddtrace from ${path}"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|^ddtrace =.*$|ddtrace = { path = \"file://${path}\" }|" datadog-lambda-python/pyproject.toml
        else
            sed -i "s|^ddtrace =.*$|ddtrace = { path = \"file://${path}\" }|" datadog-lambda-python/pyproject.toml
        fi
        cp -r ./*.whl datadog-lambda-python/
    elif [ "$(find . -maxdepth 1 -name "python-load-from-pip" | wc -l)" = "1" ]; then
        echo "Install ddtrace from $(cat python-load-from-pip)"

        pip_spec=$(cat python-load-from-pip)
        if [[ $pip_spec =~ ddtrace\ @\ git\+(.*)@(.*)$ ]]; then
            # Format with revision: ddtrace @ git+https://...@revision
            git_url="${BASH_REMATCH[1]}"
            git_rev="${BASH_REMATCH[2]}"
            if [[ "$OSTYPE" == "darwin"* ]]; then
                sed -i '' "s|^ddtrace =.*$|ddtrace = { git = \"${git_url}\", rev = \"${git_rev}\" }|" datadog-lambda-python/pyproject.toml
            else
                sed -i "s|^ddtrace =.*$|ddtrace = { git = \"${git_url}\", rev = \"${git_rev}\" }|" datadog-lambda-python/pyproject.toml
            fi
        elif [[ $pip_spec =~ ddtrace\ @\ git\+(.*)$ ]]; then
            # Format without revision: ddtrace @ git+https://... (defaults to main)
            git_url="${BASH_REMATCH[1]}"
            if [[ "$OSTYPE" == "darwin"* ]]; then
                sed -i '' "s|^ddtrace =.*$|ddtrace = { git = \"${git_url}\" }|" datadog-lambda-python/pyproject.toml
            else
                sed -i "s|^ddtrace =.*$|ddtrace = { git = \"${git_url}\" }|" datadog-lambda-python/pyproject.toml
            fi
        else
            echo "ERROR: Unable to parse git URL from python-load-from-pip format: $pip_spec"
            exit 1
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
