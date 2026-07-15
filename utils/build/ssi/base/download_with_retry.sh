#!/bin/bash

download_with_retry() {
    local url="$1"
    local output
    output="$(basename "$url")"

    local max_attempts=5
    local attempt
    for (( attempt = 1; attempt <= max_attempts; attempt++ )); do
        echo "[TRACE] downloading ${output} (attempt ${attempt}/${max_attempts})"
        if curl --fail --retry 3 --retry-delay 2 -sSL -o "$output" "$url" && [ -s "$output" ]; then
            return 0
        fi
        rm -f "$output"
        if [ "$attempt" -lt "$max_attempts" ]; then
            local delay
            delay="$(printf '%d.%03d' "$(( 2 ** (attempt - 1) ))" "$(( RANDOM % 1000 ))")"
            echo "[TRACE] download failed or produced an empty file; retrying in ${delay}s"
            sleep "$delay"
        fi
    done

    echo "[ERROR] ${output} is missing or empty after ${max_attempts} attempts" >&2
    return 1
}
