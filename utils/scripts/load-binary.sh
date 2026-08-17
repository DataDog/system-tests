#!/usr/bin/env bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

set -eu

if test -f ".env"; then
    # shellcheck source=/dev/null
    source .env
fi

TARGET=${1:-}
VERSION=${2:-dev}
BINARIES_DIR=${BINARIES_DIR:-binaries}
GITHUB_TOKEN=${GITHUB_TOKEN:-}

if [[ -z "$TARGET" ]]; then
    echo "Usage: $0 <target> [dev|prod|custom]" >&2
    exit 1
fi

assert_version_is_dev() {
    if [[ "$VERSION" == "dev" ]]; then
        return 0
    fi

    echo "Don't know how to load version $VERSION for $TARGET" >&2
    exit 1
}

assert_target_branch_is_not_set() {
    if [[ -z "${LIBRARY_TARGET_BRANCH:-}" ]]; then
        return 0
    fi

    echo "It is not possible to specify the '$LIBRARY_TARGET_BRANCH' target branch for $TARGET library yet" >&2
    exit 1
}

load_waf_rule_set() {
    mkdir -p "$BINARIES_DIR"
    curl --fail --location --silent --show-error \
        -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github.v3.raw" \
        --output "$BINARIES_DIR/waf_rule_set.json" \
        https://api.github.com/repos/DataDog/appsec-event-rules/contents/build/recommended.json
}

echo "Load $VERSION artifact entries for $TARGET"

case "$TARGET" in
    waf_rule_set_v1)
        exit 1
        ;;
    waf_rule_set|waf_rule_set_v2)
        assert_version_is_dev
        assert_target_branch_is_not_set
        load_waf_rule_set
        ;;
    *)
        python3 utils/scripts/stage-target-artifacts.py \
            "$TARGET" "$VERSION" \
            --binaries-dir "$BINARIES_DIR" \
            --repo-root . \
            --compatibility
        ;;
esac
