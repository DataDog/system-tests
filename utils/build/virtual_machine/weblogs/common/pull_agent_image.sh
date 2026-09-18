#!/bin/bash
# Pull the pinned Datadog Agent image from docker-compose-agent-prod.yml.
# Retries on transient GCR rate-limit / timeout errors, then falls back to
# public.ecr.aws and Docker Hub (retagging so docker-compose uses the local image).
#
# Copied to the VM by weblog provisions that also copy
# create_and_run_app_container.sh / create_and_run_app_multicontainer.sh.
# Safe no-op when the compose file is not present.

if [ -z "${BASH_VERSION:-}" ]; then
    exec /bin/bash "$0" "$@"
fi

set -e

readonly AGENT_COMPOSE="${1:-${AGENT_COMPOSE:-docker-compose-agent-prod.yml}}"
readonly DOCKER_PULL_MAX_RETRIES="${DOCKER_PULL_MAX_RETRIES:-3}"

if [ ! -f "${AGENT_COMPOSE}" ]; then
    echo "Agent compose file ${AGENT_COMPOSE} not present; skipping agent image pull"
    exit 0
fi

agent_compose_image() {
    awk '/^[[:space:]]*image:[[:space:]]*/ { print $2; exit }' "${AGENT_COMPOSE}"
}

pull_docker_image() {
    local image="$1"
    local max_retries="$2"
    local attempt=1
    local delay=5

    while [ "${attempt}" -le "${max_retries}" ]; do
        echo "Docker pull ${image} (attempt ${attempt}/${max_retries})"
        if sudo docker pull "${image}"; then
            echo "Docker pull succeeded on attempt ${attempt}: ${image}"
            return 0
        fi
        echo "Docker pull failed on attempt ${attempt}/${max_retries}: ${image}"
        if [ "${attempt}" -lt "${max_retries}" ]; then
            echo "Retrying docker pull in ${delay}s..."
            sleep "${delay}"
            delay=$((delay * 2))
        fi
        attempt=$((attempt + 1))
    done
    return 1
}

pull_agent_image() {
    local compose_image tag fallback
    compose_image="$(agent_compose_image)"
    if [ -z "${compose_image}" ]; then
        echo "Could not read agent image from ${AGENT_COMPOSE}"
        return 1
    fi

    if pull_docker_image "${compose_image}" "${DOCKER_PULL_MAX_RETRIES}"; then
        return 0
    fi

    tag="${compose_image##*:}"
    echo "Primary registry pull failed for ${compose_image}; trying alternative registries"

    for fallback in \
        "public.ecr.aws/datadog/agent:${tag}" \
        "docker.io/datadog/agent:${tag}"; do
        if pull_docker_image "${fallback}" "${DOCKER_PULL_MAX_RETRIES}"; then
            echo "Tagging ${fallback} as ${compose_image} so docker-compose uses the local image"
            sudo docker tag "${fallback}" "${compose_image}"
            return 0
        fi
    done

    echo "Docker pull failed for ${compose_image} and alternative registries"
    return 1
}

pull_agent_image
