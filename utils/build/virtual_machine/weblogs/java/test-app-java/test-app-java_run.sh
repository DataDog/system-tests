#!/bin/bash
set -e

# shellcheck disable=SC2035
sudo chmod -R 755 *

echo "Start Java app"

JETTY_VERSION=9.4.56.v20240826
JETTY_CLASSPATH="/opt/jetty-distribution-$JETTY_VERSION/lib/*:/opt/jetty-distribution-$JETTY_VERSION/lib/annotations/*:/opt/jetty-distribution-$JETTY_VERSION/lib/apache-jsp/*:/opt/jetty-distribution-$JETTY_VERSION//lib/logging/*:/opt/jetty-distribution-$JETTY_VERSION//lib/ext/*:/home/datadog:."

./compile_app.sh 5985

sudo chmod 755 create_and_run_app_service.sh
# 1:start command, 2:env variables, 3:stop command
./create_and_run_app_service.sh "java -cp $JETTY_CLASSPATH JettyServletMain" "" "kill $(ps aux | grep 'JettyServletMain' | awk '{print $2}')"

echo " Java app started DONE"
