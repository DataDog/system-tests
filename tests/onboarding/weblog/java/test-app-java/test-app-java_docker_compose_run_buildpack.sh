#!/bin/bash

tar xvf test-app-java.tar
./gradlew build
sudo ./gradlew -PdockerImageRepo=system-tests/local -PdockerImageTag=latest clean bootBuildImage
sudo -E docker-compose -f docker-compose-agent-prod.yml up -d --remove-orphans datadog
sleep 20
sudo -E docker-compose -f docker-compose.yml up -d test-app-java
sudo docker-compose logs
echo "RUN DONE"
