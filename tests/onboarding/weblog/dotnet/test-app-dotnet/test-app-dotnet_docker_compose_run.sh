#!/bin/bash

tar xvf test-app-dotnet.tar
sudo docker build --build-arg RUNTIME="bullseye-slim" -t system-tests/local .
sudo -E docker-compose -f docker-compose-agent-prod.yml up -d datadog
sleep 20
sudo -E docker-compose -f docker-compose.yml up -d test-app-dotnet
echo "RUN DONE"
