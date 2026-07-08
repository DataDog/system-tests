#!/bin/bash

set -eu

cd /usr/app

REPO_URL=https://github.com/DataDog/dd-trace-rs

OTEL_DEPS=(
    opentelemetry
    opentelemetry_sdk
    opentelemetry-http
    opentelemetry-stdout
    opentelemetry-semantic-conventions
)

align_opentelemetry() {
    for dep in "${OTEL_DEPS[@]}"; do
        cargo remove "$dep" || true
    done

    # resolve and read the opentelemetry version datadog-opentelemetry pulls in.
    otel_version=$(cargo metadata --format-version 1 \
        | jq -r '[.packages[] | select(.name == "opentelemetry") | .version] | first')

    if [[ -z "$otel_version" || "$otel_version" == "null" ]]; then
        echo "could not determine opentelemetry version from datadog-opentelemetry" >&2
        exit 1
    fi

    # pin to the matching minor and let cargo pick each crate's patch version
    otel_minor="${otel_version%.*}"
    echo "aligning opentelemetry deps to ~${otel_minor} (datadog-opentelemetry uses ${otel_version})"

    cargo add "opentelemetry@~${otel_minor}" --features logs
    cargo add "opentelemetry_sdk@~${otel_minor}" --features logs
    cargo add "opentelemetry-http@~${otel_minor}"
    cargo add "opentelemetry-stdout@~${otel_minor}" --features trace,logs
    cargo add "opentelemetry-semantic-conventions@~${otel_minor}"
}

# Fails the build if more than one (semver-incompatible) version of the
# `opentelemetry` crate ends up in the dependency graph.
#
# `opentelemetry::global::*` (the tracer provider and text map propagator set
# up once in main.rs) is keyed on the exact crate version compiled into the
# binary. If some other dependency (e.g. a git-pinned crate like
# opentelemetry-instrumentation-tower) resolves a different major/minor of
# `opentelemetry` than the one datadog-opentelemetry/tracing-opentelemetry use,
# Rust links both versions side by side as distinct types with separate global
# state. Anything using the *other* version's `global::tracer()` /
# `global::get_text_map_propagator()` silently gets a no-op tracer/propagator:
# no server spans, no inbound trace-context extraction, no errors anywhere.
# This exact bug is what made every incoming-request test fail while
# outgoing http.client spans kept working fine.
check_single_opentelemetry_version() {
    local versions
    versions=$(cargo metadata --format-version 1 \
        | jq -r '[.packages[] | select(.name == "opentelemetry") | .version] | unique | .[]')

    if [[ $(echo "$versions" | grep -c .) -gt 1 ]]; then
        echo "ERROR: multiple incompatible versions of the 'opentelemetry' crate were resolved:" >&2
        echo "$versions" | sed 's/^/  - opentelemetry /' >&2
        echo >&2
        echo "opentelemetry::global::* keeps separate state per crate version, so any" >&2
        echo "dependency using the 'wrong' version's global tracer/propagator will be" >&2
        echo "silently turned into a no-op (no server spans, no context extraction)." >&2
        echo "Align every opentelemetry* dependency (including git-pinned ones like" >&2
        echo "opentelemetry-instrumentation-tower) on the same major.minor version." >&2
        exit 1
    fi
}

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

    # bump patch (right segment); — expects MAJOR.MINOR.PATCH
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
    # cargo release requires a git repo; use sed to rewrite the workspace version directly
    sed -i "s/^version = \"${current_version}\"/version = \"${dev_version}\"/" /binaries/dd-trace-rs/Cargo.toml

    cd /usr/app
    cargo add datadog-opentelemetry --path /binaries/dd-trace-rs/datadog-opentelemetry --features metrics-http,metrics-grpc,logs-http,logs-grpc
else
    echo "install from crates.io with metrics-http and metrics-grpc features"

    # remove previous depedency on datadog-opentelemetry and add the new one from crates.io
    cargo remove datadog-opentelemetry || true
    cargo add datadog-opentelemetry --features metrics-http,metrics-grpc,logs-http,logs-grpc
fi

# align the opentelemetry deps with whatever datadog-opentelemetry resolved to
align_opentelemetry
check_single_opentelemetry_version
