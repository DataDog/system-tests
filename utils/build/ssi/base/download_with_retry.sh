#!/bin/bash

run_with_retry() {
    local description="$1"
    local max_attempts="$2"
    local retry_delay="$3"
    shift 3

    local attempt
    for (( attempt = 1; attempt <= max_attempts; attempt++ )); do
        echo "[TRACE] running ${description} (attempt ${attempt}/${max_attempts})"
        if "$@"; then
            return 0
        fi

        if (( attempt < max_attempts )); then
            echo "[WARN] ${description} failed; retrying in ${retry_delay} seconds" >&2
            sleep "$retry_delay"
        fi
    done

    echo "[ERROR] ${description} failed after ${max_attempts} attempts" >&2
    return 1
}

_download_once() {
    local url="$1"
    local output="$2"

    if curl --fail --retry 3 -sSL -o "$output" "$url" && [ -s "$output" ]; then
        return 0
    fi

    rm -f "$output"
    return 1
}

download_with_retry() {
    local url="$1"
    local output
    output="$(basename "$url")"

    run_with_retry "download ${output}" 5 0 _download_once "$url" "$output"
}
