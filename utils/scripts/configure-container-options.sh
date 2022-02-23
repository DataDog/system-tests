#!/bin/bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


##########################################################################################
# The purpose of this script is to proxy UDS to TCP for mitmproxy until we implement UDS proxy.
##########################################################################################

set -eu

echo "APM receiver socket is ${DD_APM_RECEIVER_SOCKET:-NOT_SET}"
echo "DSD receiver socket is ${DD_DOGSTATSD_SOCKET:-NOT_SET}"

if [ ${SYSTEST_SCENARIO} = "UDS" ]; then

    if [ ${SYSTEST_VARIATION} = "DEFAULT" ]; then
    
        echo "Attempting to use UDS default path"

        apt-get update
        apt-get install socat -y

        mkdir -p /var/run/datadog
        chmod -R a+rwX /var/run/datadog

        ( socat UNIX-LISTEN:/var/run/datadog/apm.socket,fork TCP:library_proxy:7126 ) &
        ( socat -u UNIX-LISTEN:/var/run/datadog/dsd.socket,fork UDP:agent:7125 ) &

        echo "Using default UDS config successfully"
        # ( socat UNIX-LISTEN:/var/run/datadog/apm.sock,fork TCP:agent:${HIDDEN_APM_PORT_OVERRIDE} ) &
        # ( socat -u UNIX-LISTEN:/var/run/datadog/dsd.sock,fork UDP:agent:${HIDDEN_DSD_PORT_OVERRIDE} ) &
    else
        echo "Using explicit UDS config"
        if [ -z ${DD_APM_RECEIVER_SOCKET+x} ]; then
            ( socat UNIX-LISTEN:${DD_APM_RECEIVER_SOCKET},fork TCP:agent:${HIDDEN_APM_PORT_OVERRIDE} ) &
        fi
        if [ -z ${DD_DOGSTATSD_SOCKET+x} ]; then
            ( socat -u UNIX-LISTEN:${DD_DOGSTATSD_SOCKET},fork UDP:agent:${HIDDEN_DSD_PORT_OVERRIDE} ) &
        fi
    fi 

fi