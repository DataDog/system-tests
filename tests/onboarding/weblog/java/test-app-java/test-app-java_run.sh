#!/bin/bash
set -e
sudo chmod -R 755 *

echo "START RUN APP"
./gradlew build
sudo cp build/libs/k8s-lib-injection-app-0.0.1-SNAPSHOT.jar /home/datadog
sudo cp test-app-java.service /etc/systemd/system/test-app-java.service
sudo systemctl daemon-reload
sudo systemctl enable test-app-java.service
sudo systemctl start test-app-java.service
sudo systemctl status test-app-java.service
ps -fea|grep java
echo "RUN DONE"