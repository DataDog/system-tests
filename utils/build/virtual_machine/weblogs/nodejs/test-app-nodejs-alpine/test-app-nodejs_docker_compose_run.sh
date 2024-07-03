#!/bin/bash
# shellcheck disable=SC2015

set -e

# shellcheck disable=SC2035
sudo chmod -R 755 *

rm -rf Dockerfile || true
cp Dockerfile.template Dockerfile || true

echo "Starting nodejs app deployment"
sudo docker build --no-cache -t system-tests/local .
if [ -f docker-compose-agent-prod.yml ]; then
    # Agent may be installed in a different way
    sudo -E docker-compose -f docker-compose-agent-prod.yml up -d --remove-orphans datadog
    sleep 30
fi
#Env variables set on the scenario definition. Write to file and load  
SCENARIO_APP_ENV="${DD_APP_ENV:-''}"
echo "$SCENARIO_APP_ENV" | tr '[:space:]' '\n' > scenario_app.env
echo "APP VARIABLES CONFIGURED FROM THE SCENARIO:"
cat scenario_app.env

sudo -E docker-compose -f docker-compose.yml up -d test-app-nodejs

echo "**************** RUNNING DOCKER SERVICES *****************" 
sudo docker-compose ps
if [ -f docker-compose-agent-prod.yml ]; then
    echo "**************** DATADOG AGENT OUTPUT ********************"
    sudo docker-compose -f docker-compose-agent-prod.yml logs datadog
fi
echo "**************** WEBLOG APP OUTPUT********************"
sudo docker-compose logs
echo "RUN DONE!"
