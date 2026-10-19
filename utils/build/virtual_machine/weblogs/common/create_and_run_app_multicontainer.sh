#!/bin/bash
# shellcheck disable=SC2015

set -e

readonly AGENT_COMPOSE="docker-compose-agent-prod.yml"
# Created by the provision when the agent must send its payloads to the mocked backend
readonly AGENT_COMPOSE_MOCKED_BACKEND="docker-compose-agent-mocked-backend.yml"
readonly AGENT_LOCK="agent.lock"
PULL_AGENT_IMAGE_SCRIPT="$(dirname "$0")/pull_agent_image.sh"
readonly PULL_AGENT_IMAGE_SCRIPT

# shellcheck disable=SC2035
sudo chmod -R 755 *

sudo systemctl start docker # Start docker service if it's not started

#workaround. Remove the system-tests cloned folder. The sources are copied to current home folder
#if we don't remove it, the dotnet restore will try to restore the system-tests folder
sudo rm -rf system-tests || true

#Build apps
sudo docker-compose -f docker-compose.yml build  --parallel

if [ -f "${AGENT_COMPOSE}" ]; then
    set -a
    # shellcheck source=/dev/null
    . "./${AGENT_LOCK}"
    set +a

    # Agent may be installed in a different way. Pull with retries before compose up
    # so GCR rate limits / timeouts do not fail the provision on the first attempt.
    bash "${PULL_AGENT_IMAGE_SCRIPT}"
    # Run with "sh": no arrays
    AGENT_COMPOSE_FILES="-f ${AGENT_COMPOSE}"
    if [ -f "${AGENT_COMPOSE_MOCKED_BACKEND}" ]; then
        AGENT_COMPOSE_FILES="${AGENT_COMPOSE_FILES} -f ${AGENT_COMPOSE_MOCKED_BACKEND}"
    fi
    # shellcheck disable=SC2086
    sudo -E docker-compose ${AGENT_COMPOSE_FILES} up -d --remove-orphans datadog --wait --wait-timeout 120
fi

#Env variables set on the scenario definition. Write to file and load  
if [ ! -f scenario_app.env ]
then
   SCENARIO_APP_ENV="${DD_APP_ENV:-''}"
    echo "$SCENARIO_APP_ENV" | tr '[:space:]' '\n' > scenario_app.env
    echo "APP VARIABLES CONFIGURED FROM THE SCENARIO:"
    cat scenario_app.env
fi
sudo -E docker-compose -f docker-compose.yml up -d --wait --wait-timeout 180 || true

echo "..:: RUNNING DOCKER SERVICES ::.." 
sudo docker-compose -f docker-compose.yml ps

echo "..:: WEBLOG APP OUTPUT ::.."
sudo docker-compose -f docker-compose.yml logs
echo "RUN DONE"
