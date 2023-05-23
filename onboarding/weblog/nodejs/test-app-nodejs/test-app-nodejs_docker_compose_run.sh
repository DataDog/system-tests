#!/bin/bash

tar xvf test-app-nodejs.tar
sudo docker build -t system-tests/local .
sudo -E docker-compose -f docker-compose-agent-prod.yml up -d datadog
sleep 20
sudo -E docker-compose -f docker-compose.yml up -d test-app-nodejs
echo "RUN DONE"
