#!/bin/bash

REPO_URL=https://github.com/DataDog/dd-trace-rs

set +e
if [ -e /binaries/rust-load-from-git ]; then
    rev_or_branch=$(</binaries/rust-load-from-git)

    if git clone -b "$rev_or_branch" $REPO_URL /binaries/dd-trace-rs; then
        echo "cloned $REPO_URL -b $rev_or_branch into /binaries/dd-trace-rs"
    else
        echo "git clone failed for $REPO_URL $rev_or_branch"
    fi
fi

set -eu

cd /usr/app

if [ -e /binaries/dd-trace-rs ]; then
    cargo add --path /binaries/dd-trace-rs/datadog-opentelemetry
    cargo add --path /binaries/dd-trace-rs/dd-trace

    echo "install from /binaries/dd-trace-rs"
else
    # TODO: add last release from crates.io
    cargo add --git $REPO_URL datadog-opentelemetry
    cargo add --git $REPO_URL dd-trace

    echo "install from $REPO_URL"
fi

