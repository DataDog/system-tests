#!/bin/bash

echo "Starting nodejs app deployment"
tar xvf test-app-nodejs.tar 
ls
echo "Starting nodejs app deployment 222222"
sudo docker build -t system-tests/local .
sudo -E docker-compose -f docker-compose-agent-prod.yml up -d --remove-orphans datadog
sleep 20
sudo -E docker-compose -f docker-compose.yml up -d test-app-nodejs
sudo docker-compose logs
echo "RUN DONE!"