#!/bin/bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


##########################################################################################
# This is an entrypoint file that all containers run in system-tests are funneled through.
##########################################################################################

set -eu

# Zero is good!
script_status=0


echo "Configuration script executed from: ${PWD}"
BASEDIR=$(dirname $0)
echo "Configuration script location: ${BASEDIR}"

if [ ${SYSTEMTESTS_SCENARIO:-DEFAULT} = "CGROUP" ]; then
    echo "Get cgroup info"
    cat /proc/self/cgroup > /var/log/system-tests/weblog.cgroup

elif [ ${SYSTEMTESTS_SCENARIO:-DEFAULT} = "UDS" ]; then

    export EXPECTED_APM_SOCKET=${DD_APM_RECEIVER_SOCKET:-/var/run/datadog/apm.socket}
    echo "Setting up UDS with ${EXPECTED_APM_SOCKET}."
    
    export SOCKET_DIR=$(echo ${EXPECTED_APM_SOCKET} | sed 's|\(.*\)/.*|\1|')
    mkdir -p ${SOCKET_DIR}
    chmod -R a+rwX ${SOCKET_DIR}

    ( socat -d -d UNIX-LISTEN:${EXPECTED_APM_SOCKET},fork TCP:library_proxy:${HIDDEN_APM_PORT_OVERRIDE:-7126} > /var/log/system-tests/uds-socat.log 2>&1 ) &

    attempts=$((14))
    while [ ! grep -q "listening on" "/var/log/system-tests/uds-socat.log" ]
    do
        sleep 0.5
        attempts=$((attempts-1))
        if [ $attempts -lt 1 ]; then
            echo "Unable to verify creation of ${EXPECTED_APM_SOCKET}."
            script_status=1
            break
        fi

    done

    # Give everything a quick second to finish in the background
    sleep 1

fi

if [ $script_status -ne 0 ]; then
    exit ${script_status}
else
    # the ultimate entry point, defined in the original Dockerfile
    ./app.sh
fi
