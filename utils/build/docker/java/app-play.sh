#!/bin/sh

set -eu
# shellcheck disable=SC2086
exec java -Xmx362m -javaagent:/app/dd-java-agent.jar -cp "/app/lib/*" play.core.server.ProdServerStart /app/ ${APP_EXTRA_ARGS:-}
