#!/bin/bash

set -eu

cd /usr/app

REPO_URL=https://github.com/DataDog/dd-trace-rs
PROD_TAG=datadog-opentelemetry-v0.2.1

if [ -e /binaries/rust-load-from-git ]; then
    rev_or_branch=$(</binaries/rust-load-from-git)

    git clone -b "$rev_or_branch" "$REPO_URL" /binaries/dd-trace-rs
    echo "Cloned $REPO_URL -b $rev_or_branch into /binaries/dd-trace-rs"
fi

if [ -e /binaries/dd-trace-rs ]; then
    cargo add --path /binaries/dd-trace-rs/datadog-opentelemetry --features metrics-http,metrics-grpc

    echo "install from /binaries/datadog-opentelemetry with metrics-http and metrics-grpc features"
    echo "dev" > SYSTEM_TESTS_LIBRARY_VERSION_MODE
else
    # TODO: add lastest release from crates.io
    cargo add --git "$REPO_URL" --tag "$PROD_TAG" datadog-opentelemetry --features metrics-http,metrics-grpc

    echo "install from --git $REPO_URL --tag $PROD_TAG with metrics-http and metrics-grpc features"
    echo "release" > SYSTEM_TESTS_LIBRARY_VERSION_MODE
fi

