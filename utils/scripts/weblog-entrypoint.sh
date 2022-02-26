#!/bin/bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


##########################################################################################
# This is an entrypoint file that all containers run in system-tests are funneled through.
##########################################################################################

set -eu

/configuration-scripts/configure-app-container.sh
echo "Argument count: ${#:-ZERO}"
echo "Arguments passed: ${@:-MUST_SPECIFY_ARGUMENTS_VIA_DOCKERFILE_CMD}"

eval "${@:-MUST_SPECIFY_ARGUMENTS_VIA_DOCKERFILE_CMD}"
