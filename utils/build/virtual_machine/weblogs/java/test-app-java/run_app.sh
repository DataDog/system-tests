#!/bin/bash
set -e

JETTY_CLASSPATH="/opt/jetty-classpath/*:."
java -cp "$JETTY_CLASSPATH" JettyServletMain
