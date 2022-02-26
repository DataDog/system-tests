#!/bin/bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


##########################################################################################
# The purpose of this script is to proxy UDS to TCP for mitmproxy until we implement UDS proxy.
##########################################################################################

set -eu

if [ ${SYSTEST_SCENARIO} = "UDS" ]; then

    export EXPECTED_APM_SOCKET=${DD_APM_RECEIVER_SOCKET:-/var/run/datadog/apm.socket}
    export EXPECTED_DSD_SOCKET=${DD_DOGSTATSD_SOCKET:-/var/run/datadog/dsd.socket}

    echo "Setting up UDS with ${EXPECTED_APM_SOCKET} and ${EXPECTED_DSD_SOCKET}"

    if [ ${EXPECTED_APM_SOCKET} = "/var/run/datadog/apm.socket" ]; then

        echo "Attempting to use UDS default path"

        mkdir -p /var/run/datadog
        chmod -R a+rwX /var/run/datadog

        ( socat UNIX-LISTEN:${EXPECTED_APM_SOCKET},fork TCP:library_proxy:${HIDDEN_APM_PORT_OVERRIDE:-7126} ) &
        ( socat -u UNIX-LISTEN:${EXPECTED_DSD_SOCKET},fork UDP:agent:${HIDDEN_DSD_PORT_OVERRIDE:-7125} ) &     
    else
        echo "Using explicit UDS config"
        if [ -z ${DD_APM_RECEIVER_SOCKET+x} ]; then
            ( socat UNIX-LISTEN:${EXPECTED_APM_SOCKET},fork TCP:agent:${HIDDEN_APM_PORT_OVERRIDE} ) &
        fi
        if [ -z ${DD_DOGSTATSD_SOCKET+x} ]; then
            ( socat -u UNIX-LISTEN:${EXPECTED_DSD_SOCKET},fork UDP:agent:${HIDDEN_DSD_PORT_OVERRIDE} ) &
        fi
    fi 

    if test -f "${EXPECTED_APM_SOCKET}"; then
        echo "[SUCCESS] APM receiver socket listening at ${EXPECTED_APM_SOCKET}"
    else
        echo "[FAILURE] APM receiver socket not bound to ${EXPECTED_APM_SOCKET}"
    fi

    if test -f "${EXPECTED_DSD_SOCKET}"; then
        echo "[SUCCESS] DSD receiver socket listening at ${EXPECTED_DSD_SOCKET}"
    else
        echo "[FAILURE] DSD receiver socket not bound to ${EXPECTED_DSD_SOCKET}"
    fi

fi
