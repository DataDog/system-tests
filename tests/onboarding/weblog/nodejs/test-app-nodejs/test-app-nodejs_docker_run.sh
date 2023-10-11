#!/bin/bash

tar xvf test-app-nodejs.tar
sudo docker build -t system-tests/local .
sudo docker run  --name test_nodejs -d -p 5985:18080 system-tests/local
sudo docker logs test_nodejs 
echo "RUN DONE nodejs"
