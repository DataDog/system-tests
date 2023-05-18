#!/bin/bash

tar xvf test-app-nodejs.tar
sudo docker build -t system-tests/local .
sudo docker run -d -p 5985:18080 system-tests/local

echo "RUN DONE"
