#!/bin/bash

set -e
sudo chmod -R 755 *
cp dd-lib-ruby-init-test-rails/* .
sudo docker build -t system-tests/local .
sudo -E docker-compose -f docker-compose-agent-prod.yml up -d --remove-orphans datadog
sleep 20
sudo -E docker-compose -f docker-compose.yml up -d test-app-ruby
sudo docker-compose ps
sudo docker-compose logs --since=1h
echo "RUN DONE"
