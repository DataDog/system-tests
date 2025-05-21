#!/bin/bash

# this script is temporary until repo is public
set +e
if [ -e /binaries/rust-load-from-git ]; then
    rev_or_branch=$(</binaries/rust-load-from-git)

    echo "trying to clone git@github.com:DataDog/dd-trace-rs.git - '$rev_or_branch'"

    git clone git@github.com:DataDog/dd-trace-rs.git /binaries/dd-trace-rs
    cd /binaries/dd-trace-rs

    if [[ -n "$rev_or_branch" ]]; then
        git checkout "$rev_or_branch"
    fi

    echo "cloned git@github.com:DataDog/dd-trace-rs.git && checkout $rev_or_branch"
fi

set -eu

cd /usr/app

if [ -e /binaries/dd-trace-rs ]; then
    cargo add --path /binaries/dd-trace-rs/datadog-opentelemetry
    cargo add --path /binaries/dd-trace-rs/dd-trace

    echo "install from /binaries/dd-trace-rs"
else
    cargo add --git https://github.com/DataDog/dd-trace-rs datadog-opentelemetry
    cargo add --git https://github.com/DataDog/dd-trace-rs dd-trace

    echo "install from https://github.com/DataDog/dd-trace-rs"

fi

