#!/bin/bash

set -eu

cd /usr/app

REPO_URL=https://github.com/DataDog/dd-trace-rs

if [ -e /binaries/rust-load-from-git ]; then
    rev_or_branch=$(</binaries/rust-load-from-git)

    echo "Clone $REPO_URL -b $rev_or_branch into /binaries/dd-trace-rs"
    git clone -b "$rev_or_branch" "$REPO_URL" /binaries/dd-trace-rs
fi

if [ -e /binaries/dd-trace-rs ]; then
    echo "install from /binaries/datadog-opentelemetry"
    cargo add --path /binaries/dd-trace-rs/datadog-opentelemetry --features metrics-http,metrics-grpc
else
    # use verson from the main branch
    echo "install from --git $REPO_URL from the main branch"
    cargo add --git "$REPO_URL" datadog-opentelemetry --features metrics-http,metrics-grpc
fi

