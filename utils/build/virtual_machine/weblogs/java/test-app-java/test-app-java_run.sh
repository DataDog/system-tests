#!/bin/bash
set -e

# shellcheck disable=SC2035
sudo chmod -R 755 *

echo "Start Java app"

./compile_app.sh 5985
sudo mkdir -p /opt/jetty-classpath
sudo cp -r jetty-classpath/. /opt/jetty-classpath

sudo chmod 755 create_and_run_app_service.sh

JETTY_CLASSPATH="/opt/jetty-classpath/*:."
./create_and_run_app_service.sh "java -cp $JETTY_CLASSPATH JettyServletMain"

echo " Java app started DONE"
