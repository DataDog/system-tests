#!/bin/bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

set -eu

if [[ ${1:-} =~ ^[A-Z0-9_]+$ ]]; then
    # Retro comp: if the first argument is a list of capital letters, then we consider it's a scenario name
    # and we add the -S option, telling pytest that's a scenario name
    RUNNER_ARGS="-S $@"
else
    RUNNER_ARGS=$@
fi

# clean any pycache folder
find utils tests -type d -name '__pycache__'  -prune -exec rm -rf {} +

if [[ -z "${IN_NIX_SHELL:-}" ]]; then
   source venv/bin/activate
fi

pytest $RUNNER_ARGS
