#!/bin/bash
set -e

# shellcheck disable=SC2035
sudo chmod -R 755 *

echo "Start Java app"

JETTY_VERSION=9.4.56.v20240826
JETTY_CLASSPATH="/opt/jetty-distribution-$JETTY_VERSION/lib/*:/opt/jetty-distribution-$JETTY_VERSION/lib/annotations/*:/opt/jetty-distribution-$JETTY_VERSION/lib/apache-jsp/*:/opt/jetty-distribution-$JETTY_VERSION//lib/logging/*:/opt/jetty-distribution-$JETTY_VERSION//lib/ext/*:."

./compile_app.sh 5985

sudo chmod 755 create_and_run_app_service.sh
./create_and_run_app_service.sh "java -cp $JETTY_CLASSPATH JettyServletMain"

echo " Java app started DONE"