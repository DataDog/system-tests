#!/usr/bin/env bash
# Logs in to Docker Hub (if credentials are provided) and pulls the images
# listed in compose.yaml, retrying on failure.
#
# When a command fails, unless the error is known to not be retryable, the command will be retried
#
# Expects DOCKERHUB_USERNAME / DOCKERHUB_TOKEN in the environment (may be empty).

set -euo pipefail

# Backoff delay (seconds) indexed by attempt number (1-based)
# since github action
BACKOFF_SECONDS=(10 20 40 80 160 320 320 320 320 320 320 320 320 320 320 320)
MAX_ATTEMPTS="${#BACKOFF_SECONDS[@]}"

# Error patterns that should never be retried (auth/permission/not-found errors
# won't fix themselves on a retry).
NON_RETRYABLE_PATTERNS=(
  "incorrect username or password"
  "unauthorized"
  "unknown command: docker compose"
  "no configuration file provided: not found"
  "empty compose file"
  "yaml: construct errors"
  "failed to resolve reference"
)

retry_with_timeout() {
  local description="$1"
  local timeout_seconds="$2"
  shift 2

  local attempt=1
  local retry_wait_seconds
  local output_file
  output_file="$(mktemp)"
  trap 'rm -f "${output_file}"' RETURN

  while true; do
    echo "${description} (attempt ${attempt}/${MAX_ATTEMPTS}, timeout ${timeout_seconds}s)..."

    # Both save the output in output_file and print it to stdout.
    # exit function if the command succeed
    if timeout "${timeout_seconds}" "$@" 2>&1 | tee "${output_file}"; then
      return 0
    fi

    for pattern in "${NON_RETRYABLE_PATTERNS[@]}"; do
      if grep -q "${pattern}" "${output_file}"; then
        echo "${description} failed with a non-retryable error: ${pattern}"
        return 1
      fi
    done

    echo "${description} failed (attempt ${attempt}/${MAX_ATTEMPTS})"
    if [ "${attempt}" -ge "${MAX_ATTEMPTS}" ]; then
      echo "${description} failed after ${attempt} attempts"
      return 1
    fi

    retry_wait_seconds="${BACKOFF_SECONDS[attempt - 1]}"
    attempt=$((attempt + 1))

    echo "retrying in ${retry_wait_seconds}s..."
    sleep "${retry_wait_seconds}"
  done
}

docker_login() {
  echo "${DOCKERHUB_TOKEN}" | docker login --username "${DOCKERHUB_USERNAME}" --password-stdin
}

if [ -n "${DOCKERHUB_USERNAME:-}" ] && [ -n "${DOCKERHUB_TOKEN:-}" ]; then
  export -f docker_login  # makes the function docker_login available in any child process spawned from it
  retry_with_timeout "Logging in to Docker Hub" 60 bash -c docker_login
fi

retry_with_timeout "Running docker compose pull" 900 docker compose --progress plain pull
