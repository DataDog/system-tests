#!/bin/bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


##########################################################################################
# The purpose of this script is to proxy UDS to TCP for mitmproxy until we implement UDS proxy.
##########################################################################################

set -eu

if [ -z ${DD_APM_RECEIVER_SOCKET+x} ]; then
    ( socat UNIX-LISTEN:/tmp/apm.sock,fork TCP:agent:8126 ) &
    
if [ -z ${DD_DOGSTATSD_SOCKET+x} ]; then
    ( socat -u UNIX-LISTEN:/tmp/dsd.sock,fork UDP:agent:8125 ) &
