#!/bin/bash
set -e

# shellcheck disable=SC2035
sudo chmod -R 755 * || chmod -R 755 * 

echo "START RUN APP"
./gradlew build

#This is the output for the app service
sudo touch /home/datadog/app-std.out
sudo chmod 777 /home/datadog/app-std.out

sudo cp build/libs/k8s-lib-injection-app-0.0.1-SNAPSHOT.jar /home/datadog
sudo cp test-app.service /etc/systemd/system/test-app.service
sudo systemctl daemon-reload
sudo systemctl enable test-app.service
sudo systemctl start test-app.service
sudo systemctl status test-app.service
sleep 5
cat /home/datadog/app-std.out

echo "RUN DONE"