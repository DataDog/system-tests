#!/bin/bash
set -e

JETTY_VERSION=9.4.56.v20240826
JETTY_CLASSPATH="/opt/jetty-distribution-$JETTY_VERSION/lib/*:/opt/jetty-distribution-$JETTY_VERSION/lib/annotations/*:/opt/jetty-distribution-$JETTY_VERSION/lib/apache-jsp/*:/opt/jetty-distribution-$JETTY_VERSION//lib/logging/*:/opt/jetty-distribution-$JETTY_VERSION//lib/ext/*:."
java -cp "$JETTY_CLASSPATH" JettyServletMain