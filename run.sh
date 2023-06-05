#!/usr/bin/env bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

set -eux

DOCKER_MODE="${DOCKER_MODE:-0}"

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -d|--docker) DOCKER_MODE=1;;
        *)
            break
            ;;
    esac
    shift
done

FIRST_ARGUMENT=${1:-DEFAULT}
if [[ $FIRST_ARGUMENT =~ ^[A-Z0-9_]+$ ]]; then
    export SYSTEMTESTS_SCENARIO=$FIRST_ARGUMENT
    export RUNNER_ARGS="tests/"
else
    # Let user choose the target
    export SYSTEMTESTS_SCENARIO="CUSTOM"
    export RUNNER_ARGS=$@
fi

if [[ "${SYSTEMTESTS_SCENARIO}" == 'DEFAULT' ]]; then
    SYSTEMTESTS_LOG_DIR='logs'
else
    SYSTEMTESTS_LOG_DIR="logs_$(echo "${SYSTEMTESTS_SCENARIO}" | tr '[:upper:]' '[:lower:]' )"
fi

if [[ "${DOCKER_MODE}" == 1 ]]; then
    exec docker run \
        --network system-tests_default \
        --rm -it \
        -v "${PWD}"/.env:/app/.env \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v "${PWD}/${SYSTEMTESTS_LOG_DIR}":"/app/${SYSTEMTESTS_LOG_DIR}" \
        -e WEBLOG_HOST=weblog \
        -e WEBLOG_PORT=7777 \
        -e AGENT_HOST=agent \
        -e HOST_PROJECT_DIR="${PWD}" \
        --name system-tests-runner \
        system_tests/runner ./run.sh ${SYSTEMTESTS_SCENARIO} ${RUNNER_ARGS}
fi

# clean any pycache folder
find utils tests -type d -name '__pycache__'  -prune -exec rm -rf {} +

if [[ -z "${IN_NIX_SHELL:-}" ]]; then
   source venv/bin/activate
fi

pytest $RUNNER_ARGS
