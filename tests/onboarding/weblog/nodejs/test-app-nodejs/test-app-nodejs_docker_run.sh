#!/bin/bash

[  -z "$DD_DOCKER_LOGIN_PASS" ] && echo "Skipping docker loging. Consider set the variable DOCKER_LOGIN and DOCKER_LOGIN_PASS" || echo $DD_DOCKER_LOGIN_PASS | sudo docker login --username $DD_DOCKER_LOGIN --password-stdin 

tar xvf test-app-nodejs.tar
sudo docker build -t system-tests/local .
sudo docker run  --name test_nodejs -d -p 5985:18080 system-tests/local
sudo docker logs test_nodejs 
echo "RUN DONE nodejs"
