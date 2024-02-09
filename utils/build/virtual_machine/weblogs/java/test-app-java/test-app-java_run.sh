#!/bin/bash
set -e
sudo chmod -R 755 *

echo "START RUN APP"
./gradlew build
sudo cp build/libs/k8s-lib-injection-app-0.0.1-SNAPSHOT.jar /home/datadog
sudo cp test-app.service /etc/systemd/system/test-app.service
sudo systemctl daemon-reload
sudo systemctl enable test-app.service
sudo systemctl start test-app.service
sudo systemctl status test-app.service
ps -fea|grep java
echo "RUN DONE"