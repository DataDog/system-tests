#!/bin/bash

tar xvf test-app-dotnet.tar
sudo docker build --build-arg RUNTIME="bullseye-slim" -t system-tests/local .
sudo docker run -d -p 5985:18080 system-tests/local

echo "RUN DONE"
