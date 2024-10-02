#!/bin/bash
set -e

# shellcheck disable=SC2035
sudo chmod -R 755 *

echo "START Java APP"

FILE=jetty-distribution-9.4.56.v20240826.tar.gz
if [ -f "$FILE" ]; then
    echo "Jetty already downloaded."
else 
    wget -q https://repo1.maven.org/maven2/org/eclipse/jetty/jetty-distribution/9.4.56.v20240826/jetty-distribution-9.4.56.v20240826.tar.gz
    sudo tar -xf jetty-distribution-9.4.56.v20240826.tar.gz -C /opt/
fi

JETTY_CLASSPATH="/opt/jetty-distribution-9.4.56.v20240826/lib/*:/opt/jetty-distribution-9.4.56.v20240826/lib/annotations/*:/opt/jetty-distribution-9.4.56.v20240826/lib/apache-jsp/*:/opt/jetty-distribution-9.4.56.v20240826//lib/logging/*:/opt/jetty-distribution-9.4.56.v20240826//lib/ext/*:."
FILE=JettyServletMain.class
if [ -f "$FILE" ]; then
    echo "App already compiled."
else 
    sudo sed -i "s/18080/5985/g" JettyServletMain.java
    javac -cp "$JETTY_CLASSPATH" JettyServletMain.java
    sudo cp JettyServletMain.class /home/datadog
fi

sudo chmod 755 create_and_run_app_service.sh
./create_and_run_app_service.sh "java -cp $JETTY_CLASSPATH JettyServletMain"

echo "RUN Java DONE"