#!/bin/bash

set -e

[[ ! -z "$DD_DOCKER_LOGIN_PASS" ]] && echo $DD_DOCKER_LOGIN_PASS | sudo docker login --username $DD_DOCKER_LOGIN --password-stdin || echo "Skipping docker loging. Consider set the variable DOCKER_LOGIN and DOCKER_LOGIN_PASS"

sudo chmod -R 755 *

sudo docker build --build-arg RUNTIME="bullseye-slim" -t system-tests/local .
sudo -E docker-compose -f docker-compose-agent-prod.yml up -d --remove-orphans datadog
sleep 30
sudo -E docker-compose -f docker-compose.yml up -d test-app-dotnet

echo "**************** RUNNING DOCKER SERVICES *****************" 
sudo docker-compose ps
echo "**************** DATADOG AGENT OUTPUT ********************"
sudo docker-compose -f docker-compose-agent-prod.yml logs datadog
echo "**************** WEBLOG APP OUTPUT********************"
sudo docker-compose logs

echo "RUN DONE"
