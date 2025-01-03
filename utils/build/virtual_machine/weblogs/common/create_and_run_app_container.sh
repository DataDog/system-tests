#!/bin/bash
# shellcheck disable=SC2015

set -e

# shellcheck disable=SC2035
sudo chmod -R 755 *

rm -rf Dockerfile || true
cp Dockerfile.template Dockerfile || true

sudo systemctl start docker # Start docker service if it's not started

#workaround. Remove the system-tests cloned folder. The sources are copied to current home folder
#if we don't remove it, the dotnet restore will try to restore the system-tests folder
sudo rm -rf system-tests || true

#The parameter RUNTIME is used only for dotnet
sudo docker build --no-cache --build-arg RUNTIME="bullseye-slim" -t system-tests/local .

if [ -f docker-compose-agent-prod.yml ]; then
    # Agent may be installed in a different way
    sudo -E docker-compose -f docker-compose-agent-prod.yml up -d --remove-orphans datadog --wait --wait-timeout 120
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
