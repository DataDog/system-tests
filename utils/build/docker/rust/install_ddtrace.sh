#!/bin/bash

set -eu

cd /usr/app

REPO_URL=https://github.com/DataDog/dd-trace-rs
PROD_TAG=v0.0.2

if [ -e /binaries/rust-load-from-git ]; then
    rev_or_branch=$(</binaries/rust-load-from-git)

    git clone -b "$rev_or_branch" "$REPO_URL" /binaries/dd-trace-rs
    echo "Cloned $REPO_URL -b $rev_or_branch into /binaries/dd-trace-rs"
fi

if [ -e /binaries/dd-trace-rs ]; then
    cargo add --path /binaries/dd-trace-rs/datadog-opentelemetry

    # TODO: remove once new dd-trace-rs version is merged
    if [ -e /binaries/dd-trace-rs/dd-trace ]; then
        # Replace datadog_opentelemetry::core:: with dd_trace::
        sed -i 's/datadog_opentelemetry::core::/dd_trace::/g' src/main.rs

        cargo add --path /binaries/dd-trace-rs/dd-trace
    fi

    echo "install from /binaries/dd-trace-rs"
else
    # TODO: add lastest release from crates.io
    cargo add --git "$REPO_URL" --tag "$PROD_TAG" datadog-opentelemetry

    echo "install from --git $REPO_URL --tag $PROD_TAG"
fi

