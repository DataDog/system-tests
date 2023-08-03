#!/bin/bash
echo "START RUN APP"
tar xvf test-app-java.tar
./gradlew build
cp build/libs/k8s-lib-injection-app-0.0.1-SNAPSHOT.jar .
sudo sed -i "s/MY_USER/$(whoami)/g" test-app-java.service 
sudo cp test-app-java.service /etc/systemd/system/test-app-java.service
sudo systemctl daemon-reload
sudo systemctl enable test-app-java.service
sudo systemctl start test-app-java.service
sudo systemctl status test-app-java.service
ps -fea|grep java
echo "RUN DONE"