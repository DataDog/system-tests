#!/bin/bash
# shellcheck disable=SC2015

set -e

# shellcheck disable=SC2035
sudo chmod -R 755 *

sudo systemctl start docker # Start docker service if it's not started

#workaround. Remove the system-tests cloned folder. The sources are copied to current home folder
#if we don't remove it, the dotnet restore will try to restore the system-tests folder
sudo rm -rf system-tests || true

#Build app python 3_12
sudo docker build --no-cache -t system-tests/python_3_12  -f Dockerfile.python_3_12 .

#Build app python 3_11
sudo docker build --no-cache -t system-tests/python_3_11  -f Dockerfile.python_3_11 .

#Build reverse proxy
sudo docker build -t reverseproxy:latest -f Dockerfile.reverseproxy .

#Env variables set on the scenario definition. Write to file and load  
if [ ! -f scenario_app.env ]
then
   SCENARIO_APP_ENV="${DD_APP_ENV:-''}"
    echo "$SCENARIO_APP_ENV" | tr '[:space:]' '\n' > scenario_app.env
    echo "APP VARIABLES CONFIGURED FROM THE SCENARIO:"
    cat scenario_app.env
fi
sudo -E docker-compose -f docker-compose-reverseproxy.yaml up -d

echo "..:: RUNNING DOCKER SERVICES ::.." 
sudo docker-compose -f docker-compose-reverseproxy.yaml ps

echo "..:: WEBLOG APP OUTPUT ::.."
sudo docker-compose -f docker-compose-reverseproxy.yaml logs
echo "RUN DONE"
