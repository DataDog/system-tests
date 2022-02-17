#!/bin/bash

set -eu

bash /system-tests/utils/scripts/configure-container-options.sh
java -javaagent:/app/dd-java-agent.jar -jar /app/myproject-0.0.1-SNAPSHOT.jar --server.port=7777
