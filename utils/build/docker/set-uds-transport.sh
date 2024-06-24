#!/bin/bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

unset DD_TRACE_AGENT_PORT
unset DD_AGENT_HOST

export SOCKET_DIR=$(echo ${DD_APM_RECEIVER_SOCKET} | sed 's|\(.*\)/.*|\1|')
echo "Setting up UDS with $DD_APM_RECEIVER_SOCKET"

mkdir -p ${SOCKET_DIR}
chmod -R a+rwX ${SOCKET_DIR}

(socat -d -d UNIX-LISTEN:${DD_APM_RECEIVER_SOCKET},fork TCP:proxy:8126 >/var/log/system-tests/uds-socat.log 2>&1) &

# Zero is good!
script_status=1
attempts=$((14))

while [ $attempts -gt 0 ]; do
    attempts=$((attempts - 1))

    echo "Checking /var/log/system-tests/uds-socat.log"
    grep -q "listening on" "/var/log/system-tests/uds-socat.log"

    if [ $? -eq 0 ]; then
        script_status=0
        break
    fi

    sleep 0.5
done

# Give everything a quick second to finish in the background
sleep 1

if [ $script_status -ne 0 ]; then
    echo "Unable to verify creation of ${DD_APM_RECEIVER_SOCKET}."
    exit ${script_status}
fi
