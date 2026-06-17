#!/bin/bash

set -eu

cd /binaries

# Lambda's ruby runtime keeps gems under X.Y.0 (e.g. 3.4.0), so pad the patch back on.
RUBY_VERSION=$(ruby -e 'puts RUBY_VERSION.split(".")[0..1].join(".") + ".0"')
GEM_DIR="/opt/ruby/gems/${RUBY_VERSION}"

# Source order of preference: local checkout in binaries/, then a pinned zip, else the latest release.
if [ -d "datadog-lambda-rb" ]; then
    echo "Install datadog-lambda from local source"
    cd datadog-lambda-rb
    # NOTE: The gemspec globs lib/**, so a synced-but-uncommitted checkout ships as-is.
    #       That's how we exercise unreleased lambda/tracer.
    gem build datadog-lambda
    gem install datadog-lambda-*.gem --install-dir "${GEM_DIR}" --no-document
    if [ -d "/binaries/dd-trace-rb" ]; then
        echo "Install dd-trace-rb from local source"
        cd /binaries/dd-trace-rb
        gem build datadog
        gem install datadog-*.gem --install-dir "${GEM_DIR}" --no-document
    else
        gem install datadog --install-dir "${GEM_DIR}" --no-document
    fi
elif [ "$(find . -maxdepth 1 -name '*.zip' | wc -l)" = "1" ]; then
    path=$(readlink -f "$(find . -maxdepth 1 -name '*.zip')")
    echo "Install datadog-lambda from ${path}"
    unzip "${path}" -d /opt
else
    echo "Fetching from latest GitHub release..."
    ARCH=$(uname -m | sed 's/x86_64/amd64/' | sed 's/aarch64/arm64/')
    RUBY_MINOR=$(ruby -e 'puts RUBY_VERSION.split(".")[0..1].join(".")')
    # NOTE: Release assets are datadog-lambda_ruby-<arch>-<major.minor>.zip
    #       just one-dot (3.4, not 3.4.0).
    #       The old datadog_lambda_rb-* name still resolved, but to a stale layer
    #       with no AppSec
    URL="https://github.com/DataDog/datadog-lambda-rb/releases/latest/download/datadog-lambda_ruby-${ARCH}-${RUBY_MINOR}.zip"
    echo "${URL}"
    curl -fsSLO "${URL}"
    ZIPFILE="datadog-lambda_ruby-${ARCH}-${RUBY_MINOR}.zip"
    if [ ! -f "${ZIPFILE}" ]; then
        echo "Failed to download ${ZIPFILE}"
        exit 1
    fi
    unzip -o "${ZIPFILE}" -d /opt
fi

rm -rf "${GEM_DIR}/cache"
