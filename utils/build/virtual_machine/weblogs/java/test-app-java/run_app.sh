#!/bin/bash
set -e

JETTY_CLASSPATH="/home/datadog/jetty-classpath/*:."
java -cp "$JETTY_CLASSPATH" JettyServletMain
