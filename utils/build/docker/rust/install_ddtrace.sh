#!/bin/bash

set -eu

if [ -e /binaries/rust-load-from-git ]; then
    rev_or_branch=$(</binaries/rust-load-from-git)
    git clone git@github.com:DataDog/dd-trace-rs.git /binaries/dd-trace-rs
    cd /binaries/dd-trace-rs

    if [[ -n "$rev_or_branch" ]]; then
        git checkout "$rev_or_branch"
    fi
        
    echo "cloned git@github.com:DataDog/dd-trace-rs.git && checkout $rev_or_branch"
fi

cd /usr/app

if [ -e /binaries/dd-trace-rs ]; then
    cargo add --path /binaries/dd-trace-rs/datadog-opentelemetry
    cargo add --path /binaries/dd-trace-rs/dd-trace
    
    echo "install from /binaries/dd-trace-rs"
else
    cargo add datadog-opentelemetry
    cargo add dd-trace
    
    echo "install from crates.io"
    
fi

