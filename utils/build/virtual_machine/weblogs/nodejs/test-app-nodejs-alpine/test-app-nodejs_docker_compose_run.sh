#!/bin/bash
# shellcheck disable=SC2015

set -e

# shellcheck disable=SC2035
sudo chmod -R 755 *

rm -rf Dockerfile || true
cp Dockerfile.template Dockerfile || true

echo "Starting nodejs app deployment"
sudo docker build --no-cache -t system-tests/local .
sudo -E docker-compose -f docker-compose-agent-prod.yml up -d --remove-orphans datadog
sleep 30
sudo -E docker-compose -f docker-compose.yml up -d test-app-nodejs

echo "**************** RUNNING DOCKER SERVICES *****************" 
sudo docker-compose ps
echo "**************** DATADOG AGENT OUTPUT ********************"
sudo docker-compose -f docker-compose-agent-prod.yml logs datadog
echo "**************** WEBLOG APP OUTPUT********************"
sudo docker-compose logs
echo "RUN DONE!"