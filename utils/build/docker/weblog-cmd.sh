#!/bin/bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

##########################################################################################
# This is an entrypoint file that all containers run in system-tests are funneled through.
##########################################################################################

set -eu

echo "Configuration script executed from: ${PWD}"
BASEDIR=$(dirname $0)
echo "Configuration script location: ${BASEDIR}"

./app.sh
