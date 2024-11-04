#!/bin/bash
set -e

# shellcheck disable=SC2035
sudo chmod -R 755 *

echo "Compiling Java app"
JETTY_VERSION=9.4.56.v20240826
JETTY_FILE="jetty-distribution-$JETTY_VERSION.tar.gz"
PORT=$1
if [ -f "$JETTY_FILE" ]; then
    echo "Jetty already downloaded."
else
    echo "Downloading Jetty runtime"
    wget -q https://repo1.maven.org/maven2/org/eclipse/jetty/jetty-distribution/$JETTY_VERSION/jetty-distribution-$JETTY_VERSION.tar.gz
    sudo tar -xf jetty-distribution-$JETTY_VERSION.tar.gz -C /opt/
fi

mkdir jetty-classpath

find /opt/jetty-distribution-$JETTY_VERSION/lib -iname '*.jar' -exec cp \{\} jetty-classpath/ \;

# Causes ClassNotFound exceptions https://github.com/jetty/jetty.project/issues/4746
rm jetty-classpath/jetty-jaspi*

FILE=JettyServletMain.class
if [ -f "$FILE" ]; then
    echo "App already compiled."
else 
    sudo sed -i "s/18080/$PORT/g" JettyServletMain.java
    javac -cp "jetty-classpath/*:." JettyServletMain.java
    sudo cp JettyServletMain.class /home/datadog
fi

echo "Compiling Java app DONE"