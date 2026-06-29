#!/bin/bash
# shellcheck disable=SC2015

# Provision runs "sh create_and_run_app_container.sh" — re-exec with bash for traps/functions.
if [ -z "${BASH_VERSION:-}" ]; then
    exec /bin/bash "$0" "$@"
fi

set -e

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
readonly DIAGNOSTICS_LOG="${HOME}/dd-agent-diagnostics.log"
readonly SCRIPT_MARKER="create_and_run_app_container.sh diagnostics-v3"
readonly AGENT_COMPOSE="docker-compose-agent-prod.yml"
readonly WEBLOG_LOG_DIR="/var/log/datadog_weblog"
readonly DOCKER_BUILD_MAX_RETRIES=3

# True when the Datadog Agent is installed via its own compose file.
agent_is_enabled() {
    [ -f "${AGENT_COMPOSE}" ]
}

# ---------------------------------------------------------------------------
# Diagnostics (collected on every run, and on failure, to help debugging in CI)
# ---------------------------------------------------------------------------
_dd_agent_diagnostics_dumped=0

dump_dd_agent_diagnostics() {
    # Only dump once, and only when the agent is part of this scenario.
    if [ "$_dd_agent_diagnostics_dumped" -eq 1 ] || ! agent_is_enabled; then
        return 0
    fi
    _dd_agent_diagnostics_dumped=1

    {
        echo "..:: DD-AGENT DIAGNOSTICS (${SCRIPT_MARKER}) ::.."
        date -u '+%Y-%m-%dT%H:%M:%SZ'
        sudo docker-compose -f "${AGENT_COMPOSE}" ps 2>&1 || true
        if sudo docker inspect dd-agent >/dev/null 2>&1; then
            echo "..:: DD-AGENT HEALTH ::.."
            sudo docker inspect dd-agent --format '{{json .State.Health}}' 2>&1 || true
            echo "..:: DD-AGENT LOGS (docker logs) ::.."
            sudo docker logs dd-agent 2>&1 | tail -300 || true
        else
            echo "..:: dd-agent container not found ::.."
            sudo docker ps -a 2>&1 || true
        fi
        echo "..:: DD-AGENT LOGS (docker-compose logs) ::.."
        sudo docker-compose -f "${AGENT_COMPOSE}" logs --no-color datadog 2>&1 || true
    } 2>&1 | tee -a "${DIAGNOSTICS_LOG}"

    # Mirror diagnostics into the log folder downloaded by the test harness.
    sudo mkdir -p "${WEBLOG_LOG_DIR}" 2>/dev/null || true
    if [ -d "${WEBLOG_LOG_DIR}" ]; then
        sudo cp "${DIAGNOSTICS_LOG}" "${WEBLOG_LOG_DIR}/dd-agent-diagnostics.log" 2>/dev/null || true
        sudo chmod 644 "${WEBLOG_LOG_DIR}/dd-agent-diagnostics.log" 2>/dev/null || true
    fi
    sync 2>/dev/null || true
}

# Dump agent diagnostics on failure, then propagate the original exit status.
_on_exit() {
    local status=$?
    if [ "$status" -ne 0 ]; then
        dump_dd_agent_diagnostics
    fi
    exit "$status"
}

# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

# Make the weblog log folder writable even if provisioning fails before the
# vm_logs step, so logs can still be downloaded.
prepare_log_folder() {
    sudo mkdir -p "${WEBLOG_LOG_DIR}" 2>/dev/null || true
    sudo chmod 777 "${WEBLOG_LOG_DIR}" 2>/dev/null || true
}

prepare_sources() {
    # shellcheck disable=SC2035
    sudo chmod -R 755 *

    rm -rf Dockerfile || true
    cp Dockerfile.template Dockerfile || true

    sudo systemctl start docker # Start docker service if it's not started

    # Remove the cloned system-tests folder: sources are copied to the home
    # folder, and leaving it here makes "dotnet restore" try to restore it too.
    sudo rm -rf system-tests || true
}

# Build the weblog image, retrying on transient failures.
# RUNTIME build-arg is only used by dotnet.
build_weblog_image() {
    local attempt=1
    while [ "$attempt" -le "${DOCKER_BUILD_MAX_RETRIES}" ]; do
        if sudo docker build --no-cache --build-arg RUNTIME="bullseye-slim" -t system-tests/local .; then
            echo "Docker build succeeded on attempt ${attempt}"
            return 0
        fi
        echo "Docker build failed on attempt ${attempt}/${DOCKER_BUILD_MAX_RETRIES}"
        attempt=$((attempt + 1))
        [ "$attempt" -le "${DOCKER_BUILD_MAX_RETRIES}" ] && sleep 5
    done
    echo "Docker build failed after ${DOCKER_BUILD_MAX_RETRIES} attempts"
    exit 1
}

start_agent() {
    agent_is_enabled || return 0

    echo "DD_API_KEY=${DD_API_KEY}" > .env
    if ! sudo -E docker-compose -f "${AGENT_COMPOSE}" up -d --remove-orphans datadog --wait --wait-timeout 120; then
        echo "..:: COMPOSE_WAIT_FAILED (dd-agent unhealthy or timeout) ::.." | tee -a "${DIAGNOSTICS_LOG}" >&2
        dump_dd_agent_diagnostics
        echo "..:: Diagnostics written to ${DIAGNOSTICS_LOG} ::.." >&2
        exit 1
    fi
}

# Write the scenario-provided env variables to a file the app reads.
configure_scenario_env() {
    [ -f scenario_app.env ] && return 0

    local scenario_app_env="${DD_APP_ENV:-''}"
    echo "$scenario_app_env" | tr '[:space:]' '\n' > scenario_app.env
    echo "APP VARIABLES CONFIGURED FROM THE SCENARIO:"
    cat scenario_app.env
}

start_test_app() {
    sudo -E docker-compose -f docker-compose.yml up -d test-app
}

print_services_output() {
    echo "..:: RUNNING DOCKER SERVICES ::.."
    sudo docker-compose ps
    if agent_is_enabled; then
        echo "..:: DATADOG AGENT OUTPUT ::.."
        sudo docker-compose -f "${AGENT_COMPOSE}" logs datadog
    fi
    echo "..:: WEBLOG APP OUTPUT ::.."
    sudo docker-compose logs
    echo "RUN DONE"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    # Always dump agent diagnostics on failure too (trap is deduplicated against the success dump).
    trap _on_exit EXIT

    echo "..:: ${SCRIPT_MARKER} ::.."

    prepare_log_folder
    prepare_sources
    build_weblog_image
    start_agent
    configure_scenario_env
    start_test_app
    print_services_output

    # Capture diagnostics on success as well (no-op when the agent isn't part of the scenario).
    dump_dd_agent_diagnostics
}

main "$@"
