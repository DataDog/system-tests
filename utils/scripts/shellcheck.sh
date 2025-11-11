#!/usr/bin/env bash

set -e
set -u
set -o pipefail

function has() {
    local needle="${1}"
    shift

    local e
    # shellcheck disable=SC2053 # explicitly allow glob matching
    for e in "$@"; do [[ $needle == $e ]] && return 0; done
    return 1
}

function walk() {
    local candidate="${1}"
    shift

    local names=( "${@}" )

    while [[ -n "${candidate}" ]]; do
        for file in "${names[@]}"; do
            if [[ -e "${candidate}/${file}" ]]; then
                echo "${candidate}"
                return
            fi
        done
        candidate="${candidate%/*}"
    done
    return 1
}

function lint() {
    local files=()

    while read -r f; do
        if has "${f}" "${TODO[@]}"; then
            continue
        fi

        files+=("$f")
    done < <( find utils -name '*.sh'; ls -1 -- *.sh )

    ./venv/bin/shellcheck "${files[@]}"
}

function root() {
    walk "${PWD}" '.shellcheck' '.git'
}

function load_config() {
    # defaults
    TODO=()

    local root
    root="$(root)"

    local config="${root}/.shellcheck"

    if [[ -f "${config}" ]]; then
        # shellcheck disable=SC1090
        source "${config}"
    fi
}

function main() {
    load_config
    lint
}

if [[ "${0}" == "${BASH_SOURCE[0]}" ]]; then
    main "${@}"
fi
