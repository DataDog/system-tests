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
    JETTY_URL="https://repo1.maven.org/maven2/org/eclipse/jetty/jetty-distribution/$JETTY_VERSION/jetty-distribution-$JETTY_VERSION.tar.gz"
    for attempt in 1 2 3 4 5; do
        if command -v curl >/dev/null 2>&1; then
            curl -fsSL -o "$JETTY_FILE" "$JETTY_URL" && break
        else
            wget -q -O "$JETTY_FILE" "$JETTY_URL" && break
        fi

        rm -f "$JETTY_FILE"
        if [ "$attempt" = "5" ]; then
            echo "Failed to download Jetty runtime after $attempt attempts"
            exit 1
        fi

        echo "Retrying Jetty runtime download in 5 seconds... ($attempt/5)"
        sleep 5
    done
    sudo tar -xf "$JETTY_FILE" -C /opt/
fi

mkdir -p jetty-classpath

find /opt/jetty-distribution-$JETTY_VERSION/lib -iname '*.jar' -exec cp \{\} jetty-classpath/ \;

# Causes ClassNotFound exceptions https://github.com/jetty/jetty.project/issues/4746
rm jetty-classpath/jetty-jaspi*

FILE=JettyServletMain.class
if [ -f "$FILE" ]; then
    echo "App already compiled."
else 
    sudo sed -i "s/18080/$PORT/g" JettyServletMain.java
    javac -cp "jetty-classpath/*:." JettyServletMain.java CrashServlet.java
    sudo cp JettyServletMain.class /home/datadog
    sudo cp CrashServlet.class /home/datadog
fi

echo "Compiling Java app DONE"