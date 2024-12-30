#!/bin/bash

if [ ${UDS_WEBLOG:-} = "1" ]; then
    ./set-uds-transport.sh
fi

java -Xmx362m -javaagent:/app/dd-java-agent.jar -jar /app/myproject-0.0.1-SNAPSHOT.jar --server.port=7777
