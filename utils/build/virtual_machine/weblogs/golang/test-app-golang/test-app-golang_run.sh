#!/bin/bash
echo "START go APP"

set -e

sudo chmod 755 create_and_run_app_service.sh
./create_and_run_app_service.sh "/home/datadog/test-app-go"

echo "RUN AFTER THE SERVICE"
cat test-app.service
echo "RUN go DONE"
