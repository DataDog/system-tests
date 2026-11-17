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
    jetty_url="https://static.datadoghq.com/assets/dd-repo-tools/mirror/02f5f9c4f6b4be0e5b2640d4b5a21e2838d68143ef96c540c2ba39885b60cb62/${JETTY_FILE}"
    # wget does not retry fatal network errors such as "connection refused" (exit 4).
    attempt=1
    while [ "$attempt" -le 5 ]; do
        if wget -nv --tries=1 --timeout=30 -O "$JETTY_FILE" "$jetty_url"; then
            break
        fi
        echo "Jetty download failed (attempt ${attempt}/5)" >&2
        rm -f "$JETTY_FILE"
        if [ "$attempt" -eq 5 ]; then
            exit 1
        fi
        sleep $((attempt * 2))
        attempt=$((attempt + 1))
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