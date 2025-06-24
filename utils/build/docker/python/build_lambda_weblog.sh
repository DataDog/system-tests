#!/usr/bin/env bash

set -euo pipefail

cd binaries

CLONED_REPO=0
SKIP_BUILD=0

if [ -e "datadog-lambda-python" ]; then
    echo "datadog-lambda-python already exists, skipping clone."
elif [ "$(ls *.zip | wc -l)" = "1" ]; then
    echo "Unzipping datadog-lambda-python from existing zip file..."
    SKIP_BUILD=1
elif [ -e "datadog-lambda-python/pyproject.toml" ]; then
    echo "datadog-lambda-python already exists, skipping clone."
else
    echo "Cloning datadog-lambda-python repository..."
    git clone --depth 1 https://github.com/DataDog/datadog-lambda-python.git
    CLONED_REPO=1
fi

# Patch the ddtrace dependency in datadog-lambda-python based on the same rules as install_ddtrace.sh
if [[ $SKIP_BUILD -eq 0 ]]; then
    if [ -e "dd-trace-py" ]; then
        echo "Install from local folder /binaries/dd-trace-py"
        sed -i '' 's|^ddtrace =.*$|ddtrace = { path = "./dd-trace-py" }|' datadog-lambda-python/pyproject.toml
        cp -r dd-trace-py datadog-lambda-python/dd-trace-py
    elif [ "$(ls *.whl | wc -l)" = "1" ]; then
        path=$(readlink -f $(ls *.whl))
        echo "Install ddtrace from ${path}"
        sed -i '' "s|^ddtrace =.*$|ddtrace = { path = \"file://${path}\" }|" datadog-lambda-python/pyproject.toml
        cp -r "$(ls *.whl)" datadog-lambda-python/
    elif [ $(ls python-load-from-pip | wc -l) = 1 ]; then
        echo "Install ddtrace from $(cat python-load-from-pip)"

        pip_spec=$(cat python-load-from-pip)
        if [[ $pip_spec =~ ddtrace\ @\ git\+(.*)@(.*)$ ]]; then
            # Format with revision: ddtrace @ git+https://...@revision
            git_url="${BASH_REMATCH[1]}"
            git_rev="${BASH_REMATCH[2]}"
            sed -i '' "s|^ddtrace =.*$|ddtrace = { git = \"${git_url}\", rev = \"${git_rev}\" }|" datadog-lambda-python/pyproject.toml
        elif [[ $pip_spec =~ ddtrace\ @\ git\+(.*)$ ]]; then
            # Format without revision: ddtrace @ git+https://... (defaults to main)
            git_url="${BASH_REMATCH[1]}"
            sed -i '' "s|^ddtrace =.*$|ddtrace = { git = \"${git_url}\" }|" datadog-lambda-python/pyproject.toml
        else
            echo "ERROR: Unable to parse git URL from python-load-from-pip format: $pip_spec"
            exit 1
        fi
    elif [ $(ls *.whl | wc -l) = 0 ]; then
        echo "Install ddtrace from pypi"
        # Keep the default ddtrace dependency in pyproject.toml
    else
        echo "ERROR: Found several wheel files in binaries/, abort."
        exit 1
    fi
    # Build the datadog-lambda-python package
    cd datadog-lambda-python
    ARCH=$(uname -m) PYTHON_VERSION=3.13 ./scripts/build_layers.sh

    mv .layers/*.zip ../
    cd ..

    # Clean up the datadog-lambda-python directory
    if [ $CLONED_REPO -eq 1 ]; then
        echo "Removing datadog-lambda-python directory..."
        rm -rf datadog-lambda-python
    else
        # Restore the original pyproject.toml if it was not cloned
        cd datadog-lambda-python
        git checkout -- pyproject.toml
        rm -rf dd-trace-py *.whl
        cd ..
    fi
fi

cd ..

# Build the Docker image
./build.sh $@

# Clean up the lambda layer zip file
if [ $SKIP_BUILD -eq 0 ]; then
    cd binaries
    echo "Removing lambda layer zip file..."
    rm -f *.zip
fi
