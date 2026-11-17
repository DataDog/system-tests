#!/bin/bash

set -euo pipefail

GITHUB_PR_TITLE=""
GITHUB_PR_BASE_SHA=""

if GITHUB_TOKEN=$(dd-octo-sts token \
    --scope DataDog/system-tests \
    --policy gitlab.github-access.read); then
    trap 'dd-octo-sts revoke -t "$GITHUB_TOKEN" >/dev/null 2>&1 || true' EXIT

    if PR_DATA=$(curl -fsS --retry 3 --retry-delay 2 --retry-connrefused \
        -H "Accept: application/vnd.github+json" \
        -H "Authorization: Bearer $GITHUB_TOKEN" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "https://api.github.com/repos/DataDog/system-tests/commits/$CI_COMMIT_SHA/pulls"); then
        if ! GITHUB_PR_TITLE=$(jq -r \
            '[.[] | select(.state == "open")] | if length == 1 then .[0].title else "" end' <<< "$PR_DATA"); then
            echo "⚠️ Unable to parse the GitHub PR title. Running all SSI languages."
            GITHUB_PR_TITLE=""
        fi
        if ! GITHUB_PR_BASE_SHA=$(jq -r \
            '[.[] | select(.state == "open")] | if length == 1 then .[0].base.sha else "" end' <<< "$PR_DATA"); then
            echo "⚠️ Unable to parse the GitHub PR base. Comparing changes with main."
            GITHUB_PR_BASE_SHA=""
        fi
    else
        echo "⚠️ Unable to read the GitHub PR title. Running all SSI languages."
    fi

    dd-octo-sts revoke -t "$GITHUB_TOKEN" || true
    trap - EXIT
    unset GITHUB_TOKEN
else
    echo "⚠️ Unable to authenticate to GitHub. Running all SSI languages."
fi

{
    printf 'GITHUB_PR_TITLE=%s\n' "$GITHUB_PR_TITLE"
    printf 'GITHUB_PR_BASE_SHA=%s\n' "$GITHUB_PR_BASE_SHA"
} > pr-title.env
