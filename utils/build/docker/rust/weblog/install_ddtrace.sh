#!/bin/bash

# Prepares the dd-trace-rs (datadog-opentelemetry) source the weblog depends on.
#
# Unlike the parametric install_ddtrace.sh, this script does NOT enable the metrics/logs gRPC
# features: the OTLP trace-export weblog only needs trace export over http/json, and pulling in
# tonic via the gRPC features raises the minimum rustc above the base image's toolchain.
#
# Resolution order:
#   1. /binaries/rust-load-from-git present -> clone that branch/ref of dd-trace-rs.
#   2. /binaries/dd-trace-rs present        -> use the pre-supplied checkout as-is.
#   3. otherwise                            -> swap the path dependency for the crates.io release.

set -eu

cd /usr/app

REPO_URL=https://github.com/DataDog/dd-trace-rs

if [ -e /binaries/rust-load-from-git ] && [ ! -e /binaries/dd-trace-rs ]; then
    rev_or_branch=$(</binaries/rust-load-from-git)
    echo "Clone $REPO_URL -b $rev_or_branch into /binaries/dd-trace-rs"
    git clone -b "$rev_or_branch" "$REPO_URL" /binaries/dd-trace-rs
fi

if [ -e /binaries/dd-trace-rs ]; then
    echo "Using dd-trace-rs from /binaries/dd-trace-rs"

    cd /binaries/dd-trace-rs

    # Stamp a -dev version so system-tests treats this as an unreleased/in-development build.
    current_version=$(cargo metadata --no-deps --format-version 1 \
        | jq -r '.packages[] | select(.name == "datadog-opentelemetry") | .version')

    IFS=. read -r major minor patch <<<"$current_version"
    if [[ -z "${minor:-}" || -z "${patch:-}" ]]; then
        echo "expected semver MAJOR.MINOR.PATCH, got: $current_version" >&2
        exit 1
    fi
    new_version="${major}.${minor}.$((patch + 1))"

    if [ -e /binaries/dd-trace-rs/.git ]; then
        dev_version="${new_version}-dev+$(git -C /binaries/dd-trace-rs rev-parse --short HEAD)"
    else
        dev_version="${new_version}-dev"
    fi

    echo "generating dev version $dev_version from $current_version"
    sed -i "s/^version = \"${current_version}\"/version = \"${dev_version}\"/" /binaries/dd-trace-rs/Cargo.toml

    cd /usr/app
else
    echo "No local dd-trace-rs checkout; using crates.io release"
    cargo remove datadog-opentelemetry || true
    cargo add datadog-opentelemetry
fi
