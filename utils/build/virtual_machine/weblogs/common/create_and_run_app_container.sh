#!/bin/bash
# shellcheck disable=SC2015

# Provision runs "sh create_and_run_app_container.sh" — re-exec with bash for traps/functions.
if [ -z "${BASH_VERSION:-}" ]; then
    exec /bin/bash "$0" "$@"
fi

set -e

readonly DIAGNOSTICS_LOG="${HOME}/dd-agent-diagnostics.log"
readonly SCRIPT_MARKER="create_and_run_app_container.sh diagnostics-v3"

_dd_agent_diagnostics_dumped=0

dump_dd_agent_diagnostics() {
    if [ "$_dd_agent_diagnostics_dumped" -eq 1 ]; then
        return 0
    fi
    if [ ! -f docker-compose-agent-prod.yml ]; then
        return 0
    fi
    _dd_agent_diagnostics_dumped=1

    {
        echo "..:: DD-AGENT DIAGNOSTICS (${SCRIPT_MARKER}) ::.."
        date -u '+%Y-%m-%dT%H:%M:%SZ'
        sudo docker-compose -f docker-compose-agent-prod.yml ps 2>&1 || true
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
        sudo docker-compose -f docker-compose-agent-prod.yml logs --no-color datadog 2>&1 || true
    } 2>&1 | tee -a "${DIAGNOSTICS_LOG}"

    sudo mkdir -p /var/log/datadog_weblog 2>/dev/null || true
    if [ -d /var/log/datadog_weblog ]; then
        sudo cp "${DIAGNOSTICS_LOG}" /var/log/datadog_weblog/dd-agent-diagnostics.log 2>/dev/null || true
        sudo chmod 644 /var/log/datadog_weblog/dd-agent-diagnostics.log 2>/dev/null || true
    fi
    sync 2>/dev/null || true
}

# Dump agent diagnostics on any failure (deduplicated if already printed)
trap 'status=$?; if [ "$status" -ne 0 ]; then dump_dd_agent_diagnostics; fi; exit "$status"' EXIT

echo "..:: ${SCRIPT_MARKER} ::.."

# Writable by log download even when provision fails before vm_logs step
sudo mkdir -p /var/log/datadog_weblog 2>/dev/null || true
sudo chmod 777 /var/log/datadog_weblog 2>/dev/null || true

# shellcheck disable=SC2035
sudo chmod -R 755 *

rm -rf Dockerfile || true
cp Dockerfile.template Dockerfile || true

sudo systemctl start docker # Start docker service if it's not started

#workaround. Remove the system-tests cloned folder. The sources are copied to current home folder
#if we don't remove it, the dotnet restore will try to restore the system-tests folder
sudo rm -rf system-tests || true

#The parameter RUNTIME is used only for dotnet
# Retry docker build up to 3 times
retry_count=0
max_retries=3
while [ $retry_count -lt $max_retries ]; do
    if sudo docker build --no-cache --build-arg RUNTIME="bullseye-slim" -t system-tests/local .; then
        echo "Docker build succeeded on attempt $((retry_count + 1))"
        break
    else
        retry_count=$((retry_count + 1))
        if [ $retry_count -lt $max_retries ]; then
            echo "Docker build failed on attempt $retry_count, retrying... ($retry_count/$max_retries)"
            sleep 5  # Wait 5 seconds before retrying
        else
            echo "Docker build failed after $max_retries attempts"
            exit 1
        fi
    fi
done

if [ -f docker-compose-agent-prod.yml ]; then
    # Agent may be installed in a different way
    echo "DD_API_KEY=${DD_API_KEY}" > .env
    if ! sudo -E docker-compose -f docker-compose-agent-prod.yml up -d --remove-orphans datadog --wait --wait-timeout 120; then
        echo "..:: COMPOSE_WAIT_FAILED (dd-agent unhealthy or timeout) ::.." | tee -a "${DIAGNOSTICS_LOG}" >&2
        dump_dd_agent_diagnostics
        echo "..:: Diagnostics written to ${DIAGNOSTICS_LOG} ::.." >&2
        exit 1
    fi
fi
#Env variables set on the scenario definition. Write to file and load
if [ ! -f scenario_app.env ]
then
   SCENARIO_APP_ENV="${DD_APP_ENV:-''}"
    echo "$SCENARIO_APP_ENV" | tr '[:space:]' '\n' > scenario_app.env
    echo "APP VARIABLES CONFIGURED FROM THE SCENARIO:"
    cat scenario_app.env
fi
sudo -E docker-compose -f docker-compose.yml up -d test-app

echo "..:: RUNNING DOCKER SERVICES ::.."
sudo docker-compose ps
if [ -f docker-compose-agent-prod.yml ]; then
    echo "..:: DATADOG AGENT OUTPUT ::.."
    sudo docker-compose -f docker-compose-agent-prod.yml logs datadog
fi
echo "..:: WEBLOG APP OUTPUT ::.."
sudo docker-compose logs
echo "RUN DONE"
