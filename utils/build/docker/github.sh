#!/usr/bin/env bash

# This file contains helper functions to interact with the GitHub API.
# It only uses basic Bash functions and curl.
# Any failure (403, 404, etc.) will exit the script with an error message.

set -euo pipefail

get_authentication_header() {
    local github_token_file="/run/secrets/github_token"
    local github_auth_header=()

    if [[ -f "$github_token_file" ]]; then
        echo "🔒 Using GitHub token for authentication" >&2
        github_auth_header=(-H "Authorization: Bearer $(<"$github_token_file")")
    fi

    echo "${github_auth_header[@]}"
}

get_latest_release() {
    local repo="$1"
    local releases
    local auth_header=()
    IFS=' ' read -r -a auth_header <<< "$(get_authentication_header)"

    if ! releases=$(curl --fail --retry 3 "${auth_header[@]}" "https://api.github.com/repos/${repo}/releases/latest"); then
        echo "❌ Failed to get latest release for ${repo}" >&2
        exit 1
    fi

    local version
    version=$(echo "$releases" | grep '"tag_name":' | sed -E 's/.*"tag_name": ?"(v?[^"]+)".*/\1/')

    echo "✅ Latest release for ${repo} is: ${version}" >&2
    echo "$version"
}
