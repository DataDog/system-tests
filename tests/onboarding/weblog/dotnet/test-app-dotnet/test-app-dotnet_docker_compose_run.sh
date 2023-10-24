#!/bin/bash

set -e
sudo chmod -R 755 *

sudo docker build --build-arg RUNTIME="bullseye-slim" -t system-tests/local .
sudo -E docker-compose -f docker-compose-agent-prod.yml up -d --remove-orphans datadog
sleep 20
sudo -E docker-compose -f docker-compose.yml up -d test-app-dotnet
echo "RUN DONE"
