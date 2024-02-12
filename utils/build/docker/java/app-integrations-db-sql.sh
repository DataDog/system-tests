#!/bin/sh
set -eu
# shellcheck disable=SC2086
export JAVA_OPTS="-javaagent:/app/dd-java-agent.jar"
sh target/bin/webapp