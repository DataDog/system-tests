#!/usr/bin/env bash

set -euo pipefail

ARCH=${ARCH:-$(uname -m)}
PYTHON_VERSION=${PYTHON_VERSION:-3.13}

if [ "$ARCH" = "x86_64" ]; then
    ARCH="amd64"
fi

cd binaries

SKIP_BUILD=0
CLONED_REPO=0

if [ -e "datadog-lambda-python" ]; then
    echo "datadog-lambda-python already exists, skipping clone."
elif [ "$(find . -maxdepth 1 -name "*.zip" | wc -l)" = "1" ]; then
    echo "Using provided datadog-lambda-python layer."
    SKIP_BUILD=1
else
    echo "Cloning datadog-lambda-python repository..."
    git clone --depth 1 https://github.com/DataDog/datadog-lambda-python.git
    CLONED_REPO=1
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
    ARCH=$ARCH PYTHON_VERSION=$PYTHON_VERSION ./scripts/build_layers.sh

    mv .layers/*.zip ../
    cd ..

    # Clean up the datadog-lambda-python directory
    if [ "$CLONED_REPO" -eq 1 ]; then
        echo "Removing datadog-lambda-python directory..."
        rm -rf datadog-lambda-python
    else
        # Restore the original pyproject.toml if it was not cloned
        cd datadog-lambda-python
        git checkout -- pyproject.toml
        rm -rf dd-trace-py ./*.whl
        cd ..
    fi
fi

cd ..
