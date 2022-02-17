#!/bin/bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


##########################################################################################
# The purpose of this script is to proxy UDS to TCP for mitmproxy until we implement UDS proxy.
##########################################################################################

set -eu

if [ ${SYSTEST_SCENARIO} = "UDS" ]; then

    if [ ${SYSTEST_VARIATION} = "DEFAULT" ]; then
    
        echo "Using default UDS config successfully"
        apt-get update
        apt-get install socat -y

        if [ -d "/var/run/datadog" ]; then
            mkdir /var/run/datadog
        fi
        
        chmod -R a+rwX /var/run/datadog
        ( socat UNIX-LISTEN:/var/run/datadog/apm.socket,fork TCP:agent:7126 ) &
        ( socat -u UNIX-LISTEN:/var/run/datadog/dsd.socket,fork UDP:agent:7125 ) &
        # ( socat UNIX-LISTEN:/var/run/datadog/apm.sock,fork TCP:agent:${HIDDEN_APM_PORT_OVERRIDE} ) &
        # ( socat -u UNIX-LISTEN:/var/run/datadog/dsd.sock,fork UDP:agent:${HIDDEN_DSD_PORT_OVERRIDE} ) &
    else
        echo "Using explicit UDS config successfully"
        if [ -z ${DD_APM_RECEIVER_SOCKET+x} ]; then
            ( socat UNIX-LISTEN:${DD_APM_RECEIVER_SOCKET},fork TCP:agent:${HIDDEN_APM_PORT_OVERRIDE} ) &
        fi
        if [ -z ${DD_DOGSTATSD_SOCKET+x} ]; then
            ( socat -u UNIX-LISTEN:${DD_DOGSTATSD_SOCKET},fork UDP:agent:${HIDDEN_DSD_PORT_OVERRIDE} ) &
        fi
    fi 

fi