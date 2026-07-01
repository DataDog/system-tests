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

# crates that merely consume the opentelemetry API (as opposed to the
# OTEL_DEPS crates themselves) and whose version <-> opentelemetry-version
# pairing has no fixed offset, so it must be looked up in the registry.
OTEL_CONSUMERS=(
    tracing-opentelemetry
    tower-otel
)

declare -A OTEL_CONSUMER_FEATURES=(
    [tower-otel]=axum
)

# look up, from the crates.io sparse index, the highest version of $1 whose
# `opentelemetry` dependency requirement matches the $2 minor (e.g. "0.32").
pick_otel_consumer_version() {
    local crate="$1" otel_minor="$2" index_path

    if [[ ${#crate} -ge 4 ]]; then
        index_path="${crate:0:2}/${crate:2:2}/${crate}"
    elif [[ ${#crate} -eq 3 ]]; then
        index_path="3/${crate:0:1}/${crate}"
    else
        index_path="${#crate}/${crate}"
    fi

    curl -sf "https://index.crates.io/${index_path}" | jq -rs --arg otel "$otel_minor" '
        [ .[] | select(.yanked != true) | select(
            (.deps[]? | select(.name == "opentelemetry") | .req) as $req
            | ($req | ltrimstr("^") | ltrimstr("~") | split(".")[0:2] | join(".")) == $otel
        ) ]
        | sort_by(.vers | split(".") | map(tonumber))
        | last
        | .vers // ""
    '
}

align_opentelemetry() {
    for dep in "${OTEL_DEPS[@]}"; do
        cargo remove "$dep" || true
    done
    for dep in "${OTEL_CONSUMERS[@]}"; do
        cargo remove "$dep" || true
    done

    # resolve and read the opentelemetry version datadog-opentelemetry pulls in.
    # cargo.lock may still hold a stale, semver-incompatible opentelemetry
    # version from a previous alignment (locked alongside the new one added
    # by the datadog-opentelemetry dependency just above) — always take the
    # highest resolved version, since that is the one the new
    # datadog-opentelemetry dependency actually requires.
    otel_version=$(cargo metadata --format-version 1 \
        | jq -r '.packages[] | select(.name == "opentelemetry") | .version' \
        | sort -V | tail -1)

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

    for dep in "${OTEL_CONSUMERS[@]}"; do
        consumer_version=$(pick_otel_consumer_version "$dep" "$otel_minor")
        if [[ -z "$consumer_version" ]]; then
            echo "could not find a $dep version compatible with opentelemetry ~${otel_minor}" >&2
            exit 1
        fi
        echo "aligning $dep to =${consumer_version} (compatible with opentelemetry ~${otel_minor})"
        if [[ -n "${OTEL_CONSUMER_FEATURES[$dep]:-}" ]]; then
            cargo add "${dep}@=${consumer_version}" --features "${OTEL_CONSUMER_FEATURES[$dep]}"
        else
            cargo add "${dep}@=${consumer_version}"
        fi
    done
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
