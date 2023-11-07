#!/bin/bash

set -e
sudo chmod -R 755 *

echo "Starting nodejs app deployment"
sudo docker build -t system-tests/local .
sudo -E docker-compose -f docker-compose-agent-prod.yml up -d --remove-orphans datadog
sleep 20
sudo -E docker-compose -f docker-compose.yml up -d test-app-nodejs
sudo docker-compose ps
sudo docker-compose logs datadog
sudo docker-compose logs test-app-nodejs
echo "RUN DONE!"