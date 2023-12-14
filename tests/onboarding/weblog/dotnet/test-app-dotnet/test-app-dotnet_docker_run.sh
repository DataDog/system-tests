#!/bin/bash

[  -z "$DD_DOCKER_LOGIN_PASS" ] && echo "Skipping docker loging. Consider set the variable DOCKER_LOGIN and DOCKER_LOGIN_PASS" || echo $DD_DOCKER_LOGIN_PASS | sudo docker login --username $DD_DOCKER_LOGIN --password-stdin 

tar xvf test-app-dotnet.tar
sudo docker build --build-arg RUNTIME="bullseye-slim" -t system-tests/local .
sudo docker run -d -p 5985:18080 system-tests/local

echo "RUN DONE"
