#!/bin/bash

tar xvf test-app-python.tar
sudo docker build -t system-tests/local .
sudo docker run  --name test_python -d -p 5985:18080 system-tests/local
sudo docker logs test_python 
echo "RUN DONE"
