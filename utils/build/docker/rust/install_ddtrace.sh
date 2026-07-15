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

fail() {
    echo "error: $*" >&2
    exit 1
}

align_opentelemetry() {
    local metadata ddtrace_package_id otel_package_id otel_version otel_minor

    for dep in "${OTEL_DEPS[@]}"; do
        cargo remove "$dep" >/dev/null 2>&1 || true
    done

    # Read the OpenTelemetry version that datadog-opentelemetry actually resolved
    # to. Looking at the first opentelemetry package in the graph is ambiguous when
    # a conflicting version is already present.
    if ! metadata=$(cargo metadata --format-version 1 2>/dev/null); then
        fail "could not resolve dependencies after installing datadog-opentelemetry. Use a tracer revision compatible with Axum's OpenTelemetry dependencies."
    fi

    ddtrace_package_id=$(jq -r '[.packages[] | select(.name == "datadog-opentelemetry") | .id] | if length == 1 then .[0] else empty end' <<<"$metadata")
    if [[ -z "$ddtrace_package_id" ]]; then
        fail "could not identify the selected datadog-opentelemetry package in the dependency graph."
    fi

    otel_package_id=$(jq -r --arg package_id "$ddtrace_package_id" '[.resolve.nodes[] | select(.id == $package_id) | .deps[] | select(.name == "opentelemetry") | .pkg] | unique | if length == 1 then .[0] else empty end' <<<"$metadata")
    if [[ -z "$otel_package_id" ]]; then
        fail "could not identify the OpenTelemetry version required by datadog-opentelemetry."
    fi

    otel_version=$(jq -r --arg package_id "$otel_package_id" '[.packages[] | select(.id == $package_id) | .version] | if length == 1 then .[0] else empty end' <<<"$metadata")

    if [[ ! "$otel_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        fail "could not determine a valid OpenTelemetry version from datadog-opentelemetry."
    fi

    # pin to the matching minor and let cargo pick each crate's patch version
    otel_minor="${otel_version%.*}"
    echo "aligning OpenTelemetry dependencies to ~${otel_minor} (datadog-opentelemetry uses ${otel_version})"

    if ! cargo add "opentelemetry@~${otel_minor}" --features logs >/dev/null 2>&1 \
        || ! cargo add "opentelemetry_sdk@~${otel_minor}" --features logs >/dev/null 2>&1 \
        || ! cargo add "opentelemetry-http@~${otel_minor}" >/dev/null 2>&1 \
        || ! cargo add "opentelemetry-stdout@~${otel_minor}" --features trace,logs >/dev/null 2>&1 \
        || ! cargo add "opentelemetry-semantic-conventions@~${otel_minor}" >/dev/null 2>&1; then
        fail "could not align Axum's OpenTelemetry dependencies to ~${otel_minor}. Update the Axum compatibility pins and retry."
    fi
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
    if ! versions=$(cargo metadata --format-version 1 2>/dev/null \
        | jq -r '[.packages[] | select(.name == "opentelemetry") | .version] | unique | .[]'); then
        fail "could not inspect the resolved OpenTelemetry dependency graph."
    fi

    if [[ $(echo "$versions" | grep -c .) -gt 1 ]]; then
        fail "incompatible OpenTelemetry versions resolved: ${versions//$'\n'/, }. Axum and datadog-opentelemetry must use one version. Use a compatible dd-trace-rs revision, or update the Axum pins for opentelemetry-instrumentation-tower, tracing-opentelemetry, and reqwest-tracing together."
    fi
}

if [ -e /binaries/rust-load-from-git ]; then
    rev_or_branch=$(</binaries/rust-load-from-git)

    echo "Clone $REPO_URL -b $rev_or_branch into /binaries/dd-trace-rs"
    if ! git clone -b "$rev_or_branch" "$REPO_URL" /binaries/dd-trace-rs >/dev/null 2>&1; then
        fail "could not clone dd-trace-rs ref '$rev_or_branch'. Check that the ref exists and is accessible."
    fi
fi

if [ -e /binaries/dd-trace-rs ]; then
    echo "install from /binaries/datadog-opentelemetry with metrics-http and metrics-grpc features"

    cd /binaries/dd-trace-rs

    # get the version from the cargo.lock
    if ! current_version=$(cargo metadata --no-deps --format-version 1 2>/dev/null \
        | jq -r '.packages[] | select(.name == "datadog-opentelemetry") | .version'); then
        fail "could not inspect datadog-opentelemetry in /binaries/dd-trace-rs."
    fi

    # bump patch (right segment); — expects MAJOR.MINOR.PATCH
    IFS=. read -r major minor patch <<<"$current_version"
    if [[ -z "${minor:-}" || -z "${patch:-}" ]]; then
        fail "could not read a MAJOR.MINOR.PATCH datadog-opentelemetry version from /binaries/dd-trace-rs (got '$current_version')."
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
    if ! cargo add datadog-opentelemetry --path /binaries/dd-trace-rs/datadog-opentelemetry --features metrics-http,metrics-grpc,logs-http,logs-grpc >/dev/null 2>&1; then
        fail "could not install datadog-opentelemetry from /binaries/dd-trace-rs. Check that the checkout contains that package."
    fi
else
    echo "install from crates.io with metrics-http and metrics-grpc features"

    # remove previous depedency on datadog-opentelemetry and add the new one from crates.io
    cargo remove datadog-opentelemetry >/dev/null 2>&1 || true
    if ! cargo add datadog-opentelemetry --features metrics-http,metrics-grpc,logs-http,logs-grpc >/dev/null 2>&1; then
        fail "could not install datadog-opentelemetry from crates.io. Check network access and the selected package version."
    fi
fi

# align the opentelemetry deps with whatever datadog-opentelemetry resolved to
align_opentelemetry
check_single_opentelemetry_version
