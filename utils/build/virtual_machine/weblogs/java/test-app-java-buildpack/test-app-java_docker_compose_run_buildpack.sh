#!/bin/bash
# shellcheck disable=SC2015

set -e

# Function to retry commands up to 3 times
retry_command() {
    local max_attempts=3
    local attempt=1
    local cmd="$*"
    
    while [ $attempt -le $max_attempts ]; do
        echo "Attempt $attempt of $max_attempts: $cmd"
        if eval "$cmd"; then
            echo "Command succeeded on attempt $attempt"
            return 0
        else
            echo "Command failed on attempt $attempt"
            if [ $attempt -eq $max_attempts ]; then
                echo "All $max_attempts attempts failed"
                return 1
            fi
            attempt=$((attempt + 1))
            sleep 5  # Wait 5 seconds before retry
        fi
    done
}

# shellcheck disable=SC2035
sudo chmod -R 755 *

[  -z "$DD_DOCKER_LOGIN_PASS" ] && echo "Skipping docker loging. Consider set the variable DOCKER_LOGIN and DOCKER_LOGIN_PASS" || echo "$DD_DOCKER_LOGIN_PASS" | sudo docker login --username "$DD_DOCKER_LOGIN" --password-stdin 

rm -rf Dockerfile || true

sudo systemctl start docker # Start docker service if it's not started

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
retry_command "sudo ./gradlew build"
retry_command "sudo ./gradlew -PdockerImageRepo=system-tests/local -PdockerImageTag=latest -PuseDockerProxy=true clean bootBuildImage"

echo "**************** RUN SERVICES*****************" 
if [ -f docker-compose-agent-prod.yml ]; then
    # Agent may be installed in a different way
    sudo -E docker-compose -f docker-compose-agent-prod.yml up -d --remove-orphans datadog
    sleep 30
fi
#Env variables set on the scenario definition. Write to file and load  
if [ ! -f scenario_app.env ]
then
   SCENARIO_APP_ENV="${DD_APP_ENV:-''}"
    echo "$SCENARIO_APP_ENV" | tr '[:space:]' '\n' > scenario_app.env
    echo "APP VARIABLES CONFIGURED FROM THE SCENARIO:"
    cat scenario_app.env
fi
echo "SERVER_PORT=18080" >> scenario_app.env
sudo -E docker-compose -f docker-compose.yml up -d test-app

echo "**************** RUNNING DOCKER SERVICES *****************" 
sudo docker-compose ps
if [ -f docker-compose-agent-prod.yml ]; then
    echo "**************** DATADOG AGENT OUTPUT ********************"
    sudo docker-compose -f docker-compose-agent-prod.yml logs datadog
fi
echo "**************** WEBLOG APP OUTPUT********************"
sudo docker-compose logs

echo "RUN DONE"
