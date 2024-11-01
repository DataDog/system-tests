#!/bin/bash
set -e

# shellcheck disable=SC2035
sudo chmod -R 755 *

echo "Start Java app"

./compile_app.sh 5985

sudo chmod 755 create_and_run_app_service.sh
./create_and_run_app_service.sh "java -cp jetty-classpath/*:. JettyServletMain"

echo " Java app started DONE"
