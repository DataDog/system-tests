#!/bin/bash
set -e

# shellcheck disable=SC2035
sudo chmod -R 755 *

echo "START Java APP"
./gradlew build

sudo cp build/libs/k8s-lib-injection-app-0.0.1-SNAPSHOT.jar /home/datadog
sudo chmod 755 create_and_run_app_service.sh
./create_and_run_app_service.sh "java -Dserver.port=5985 -jar k8s-lib-injection-app-0.0.1-SNAPSHOT.jar"

echo "RUN Java DONE"