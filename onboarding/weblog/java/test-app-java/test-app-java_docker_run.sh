#!/bin/bash

tar xvf test-app-java.tar
#sudo ./gradlew -PdockerImageRepo=system-tests -PdockerImageTag=local clean bootBuildImage
./gradlew build
sudo docker build -t system-tests/local .
sudo docker run -d -p 5985:8080 system-tests/local
#sudo docker run -d -p 5985:8080 docker.io/library/system-tests:local

echo "RUN DONE"
