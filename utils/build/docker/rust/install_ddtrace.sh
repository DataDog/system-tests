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
    echo "install from /binaries/datadog-opentelemetry with metrics-http and metrics-grpc features"

    cd /binaries/dd-trace-rs

    # get the version from the cargo.lock
    current_version=$(cargo metadata --no-deps --format-version 1 | jq -r '.packages[] | select(.name == "datadog-opentelemetry") | .version')

    # bump minor (middle segment); reset patch to 0 — expects MAJOR.MINOR.PATCH
    IFS=. read -r major minor patch <<<"$current_version"
    if [[ -z "${minor:-}" || -z "${patch:-}" ]]; then
        echo "expected semver MAJOR.MINOR.PATCH, got: $current_version" >&2
        exit 1
    fi
    new_version="${major}.$((minor + 1)).0"

    if [ -e /binaries/dd-trace-rs/.git ]; then
        dev_version="${new_version}-dev+$(git -C /binaries/dd-trace-rs rev-parse HEAD)"
    else
        dev_version="${new_version}-dev"
    fi

    echo "generating dev version $dev_version from $current_version"
    cargo release version -p datadog-opentelemetry "$dev_version" -x --no-confirm

    cd /usr/app
    cargo add datadog-opentelemetry --path /binaries/dd-trace-rs/datadog-opentelemetry --features metrics-http,metrics-grpc,logs-http,logs-grpc
else
    echo "install from crates.io with metrics-http and metrics-grpc features"

    # remove previous depedency on datadog-opentelemetry and add the new one from crates.io
    cargo remove datadog-opentelemetry || true
    cargo add datadog-opentelemetry --features metrics-http,metrics-grpc,logs-http,logs-grpc
fi

