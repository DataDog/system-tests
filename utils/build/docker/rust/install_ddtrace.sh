#!/bin/bash

set -eu

cd /usr/app

REPO_URL=https://github.com/DataDog/dd-trace-rs
PROD_TAG=v0.0.0

if [ -e /binaries/rust-load-from-git ]; then
    rev_or_branch=$(</binaries/rust-load-from-git)

    git clone -b "$rev_or_branch" "$REPO_URL" /binaries/dd-trace-rs
    echo "Cloned $REPO_URL -b $rev_or_branch into /binaries/dd-trace-rs"
fi

if [ -e /binaries/dd-trace-rs ]; then
    cargo add --path /binaries/dd-trace-rs/datadog-opentelemetry
    cargo add --path /binaries/dd-trace-rs/dd-trace

    echo "install from /binaries/dd-trace-rs"
else
    # TODO: add lastest release from crates.io
    cargo add --git "$REPO_URL" --tag "$PROD_TAG" datadog-opentelemetry
    cargo add --git "$REPO_URL" --tag "$PROD_TAG" dd-trace

    echo "install from --git $REPO_URL --tag $PROD_TAG"
fi

