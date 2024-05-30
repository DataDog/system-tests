#!/bin/bash
# shellcheck disable=SC2015

set -e

# shellcheck disable=SC2035
sudo chmod -R 755 *

[  -z "$DD_DOCKER_LOGIN_PASS" ] && echo "Skipping docker loging. Consider set the variable DOCKER_LOGIN and DOCKER_LOGIN_PASS" || echo "$DD_DOCKER_LOGIN_PASS" | sudo docker login --username "$DD_DOCKER_LOGIN" --password-stdin 

rm -rf Dockerfile || true

echo "**************** Docker system df *****************" 
sudo docker system df
echo "**************** Disk usage *****************" 
sudo df -h
echo "**************** Docker images *****************"
sudo docker images
echo "**************** Docker containers *****************" 
sudo docker ps -a
echo "**************** Docker volumes *****************" 
sudo docker volume ls 

echo "**************** BUILDING BUILDPACK *****************" 
sudo ./gradlew build
sudo ./gradlew -PdockerImageRepo=system-tests/local -PdockerImageTag=latest clean bootBuildImage

echo "**************** RUN SERVICES*****************" 
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
