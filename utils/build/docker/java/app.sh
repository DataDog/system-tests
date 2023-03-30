#!/bin/sh
set -eu
exec java -Xmx362m -javaagent:/app/dd-java-agent.jar -jar /app/app.jar ${APP_EXTRA_ARGS:-}