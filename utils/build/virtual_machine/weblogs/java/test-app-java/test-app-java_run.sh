#!/bin/bash
set -e

# shellcheck disable=SC2035
sudo chmod -R 755 * || chmod -R 755 * 

echo "START RUN APP"
./gradlew build

if ! command -v systemctl &> /dev/null
then
    cp build/libs/k8s-lib-injection-app-0.0.1-SNAPSHOT.jar /home/datadog
    chmod 755 test-app-java_daemon.sh
    chmod 777 /shared_volume/std.out
    ./test-app-java_daemon.sh start
 else
    sudo cp build/libs/k8s-lib-injection-app-0.0.1-SNAPSHOT.jar /home/datadog
    sudo cp test-app.service /etc/systemd/system/test-app.service
    sudo systemctl daemon-reload
    sudo systemctl enable test-app.service
    sudo systemctl start test-app.service
    sudo systemctl status test-app.service
fi



echo "RUN DONE"