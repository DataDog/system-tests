#!/usr/bin/env bash

set -e
set -u
set -o pipefail

function error() {
    echo "${@}" 1>&2
}

function die() {
    local rc=1

    if [[ ${1} =~ ^-?[0-9]+$ ]]; then
        rc="${1}"
        shift
    fi

    error "${@}"
    exit "${rc}"
}

function watch() {
    local src="${1}"
    shift

    fswatch -o "${src}" | while read -r count; do
        echo "== watch: ${count} changes"
        "${@}"
    done
}

function sync() {
    local src="${1}"
    local dst="${2}"

    rsync -rlt --delete --out-format '%t %o %n' "${src}/" "${dst}/"
}

function main() {
    # handle arguments
    if [[ ${#} -lt 1 ]]; then
        die 64 "usage: ${0##*/} source [destination]"
    fi

    src="${1}"
    dst="${2:-binaries/${src##*/}}"

    # check prerequisites
    if ! command -v fswatch >/dev/null 2>&1; then
        die "error: fswatch not found"
    fi

    if ! command -v rsync >/dev/null 2>&1; then
        die "error: rsync not found"
    fi

    # normalize paths
    src="${src%/}"
    dst="${dst%/}"

    # perform
    echo "= sync '${src}' to '${dst}'"
    sync "${src}" "${dst}"
    echo "= watch '${src}'"
    watch "${src}" sync "${src}" "${dst}"
}

if [[ ${0} == "${BASH_SOURCE[0]}" ]]; then
    main "${@}"
fi
