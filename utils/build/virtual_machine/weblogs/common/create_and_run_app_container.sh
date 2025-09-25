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
