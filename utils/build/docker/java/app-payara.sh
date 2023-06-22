#!/bin/sh
set -eu
# shellcheck disable=SC2086
exec java -Xmx362m -javaagent:/app/dd-java-agent.jar -jar /app/payara-micro.jar --deploy /app/app.war ${APP_EXTRA_ARGS:-}
