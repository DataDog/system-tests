#!/bin/bash
# shellcheck disable=SC2015
set -e

# shellcheck disable=SC2035
sudo chmod -R 755 *
[  -z "$DD_DOCKER_LOGIN_PASS" ] && echo "Skipping docker loging. Consider set the variable DOCKER_LOGIN and DOCKER_LOGIN_PASS" || echo "$DD_DOCKER_LOGIN_PASS" | sudo docker login --username "$DD_DOCKER_LOGIN" --password-stdin 
rm -rf Dockerfile || true
cp Dockerfile.template Dockerfile || true
./gradlew build
sudo docker build --no-cache -t system-tests/local .
if [ -f docker-compose-agent-prod.yml ]; then
    # Agent may be installed in a different way
    sudo -E docker-compose -f docker-compose-agent-prod.yml up -d --remove-orphans datadog
    sleep 30
fi
sudo -E docker-compose -f docker-compose.yml up -d test-app-java

echo "**************** RUNNING DOCKER SERVICES *****************" 
sudo docker-compose ps
if [ -f docker-compose-agent-prod.yml ]; then
    echo "**************** DATADOG AGENT OUTPUT ********************"
    sudo docker-compose -f docker-compose-agent-prod.yml logs datadog
fi
echo "**************** WEBLOG APP OUTPUT********************"
sudo docker-compose logs
echo "RUN DONE"
