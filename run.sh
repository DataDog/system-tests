#!/bin/bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

set -eu

# set .env if exists. Allow users to keep their conf via env vars
if test -f ".env"; then
    source .env
fi

if [ -z "${DD_API_KEY:-}" ]; then
    echo "DD_API_KEY is missing in env, please add it."
    exit 1
fi

FIRST_ARGUMENT=${1:-DEFAULT}
if [[ $FIRST_ARGUMENT =~ ^[A-Z0-9_]+$ ]]; then
    export SYSTEMTESTS_SCENARIO=$FIRST_ARGUMENT
    export RUNNER_ARGS="tests/"

    if [ $SYSTEMTESTS_SCENARIO = "DEFAULT" ]; then
        export SYSTEMTESTS_LOG_FOLDER=logs
    else
        export SYSTEMTESTS_LOG_FOLDER="logs_$(echo $SYSTEMTESTS_SCENARIO | tr '[:upper:]' '[:lower:]')"
    fi
else
    # Let user choose the target
    export SYSTEMTESTS_SCENARIO="CUSTOM"
    export RUNNER_ARGS=$@
    export SYSTEMTESTS_LOG_FOLDER=logs
fi

export HOST_PWD=$(pwd)

# clean any pycache folder
find utils tests -type d -name '__pycache__'  -prune -exec rm -rf {} +

# Clean logs/ folder
rm -rf $SYSTEMTESTS_LOG_FOLDER

interfaces=(agent library backend)
for interface in ${interfaces[@]}
do
    mkdir -p $SYSTEMTESTS_LOG_FOLDER/interfaces/$interface
done

mkdir -p $SYSTEMTESTS_LOG_FOLDER/docker/runner
mkdir -p $SYSTEMTESTS_LOG_FOLDER/docker/weblog/logs
chmod -R 777 $SYSTEMTESTS_LOG_FOLDER

docker inspect system_tests/weblog > $SYSTEMTESTS_LOG_FOLDER/weblog_image.json
docker inspect system_tests/agent > $SYSTEMTESTS_LOG_FOLDER/agent_image.json

source venv/bin/activate
pytest $RUNNER_ARGS